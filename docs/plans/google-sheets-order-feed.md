# Google Sheets order feed (service account)

Brief for whoever implements it. Goal: every order placed on
timechainpeptides.com appears as a row in a Google Sheet within seconds,
written directly by the API using a Google service account. No Zapier.

Read first: `services/api/app/services/order_notify.py` (the webhook
version of this — same shape, same failure rules) and
`services/api/app/services/order_export.py` (`EXPORT_COLUMNS`,
`order_export_row`, `order_notification_payload`). The Sheets feed is a
second consumer of the exact same flat row; do not invent a new schema.

## Google side (one-time, done by David or his agent with Google access)

1. In the Google Cloud project, enable the **Google Sheets API**.
2. Create a **service account** (no roles needed) and download a JSON key.
3. Create the spreadsheet. Note its ID (the long segment in the URL between
   `/d/` and `/edit`). Name the first tab `Orders`.
4. **Share the spreadsheet with the service account's `client_email`
   as Editor.** Without this every append returns HTTP 403.

## Config (services/api/app/core/config.py, .env.example)

Add three settings next to `order_notify_webhook_url`:

```python
# Google Sheets order feed. Blank spreadsheet id = feature off.
google_sheets_orders_spreadsheet_id: str = ""
google_sheets_orders_tab: str = "Orders"
# Full JSON key contents (one line). Preferred over a file path because
# hosted platforms inject env vars, not files.
google_service_account_json: str = ""
```

`.env.example` gets the same three with a comment. Never commit a real key.

## Dependency

Add `google-auth>=2.30` to `[project].dependencies` in
`services/api/pyproject.toml` and run `uv sync` (the venv is uv-managed;
there is no pip in it). `httpx` is already a runtime dependency. Do not
add `gspread` or `google-api-python-client`; the REST call is one POST.

## New module: services/api/app/services/order_sheet.py

```python
"""Append each new order to a Google Sheet via a service account."""

from __future__ import annotations

import json
import logging
import threading

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from app.core.config import get_settings
from app.services.order_export import EXPORT_COLUMNS

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_TIMEOUT_SECONDS = 10.0
_lock = threading.Lock()
_credentials = None  # cached; google-auth refreshes the token itself


def _sheets_configured() -> bool:
    s = get_settings()
    return bool(s.google_sheets_orders_spreadsheet_id.strip() and s.google_service_account_json.strip())


def _access_token() -> str:
    global _credentials
    with _lock:
        if _credentials is None:
            info = json.loads(get_settings().google_service_account_json)
            _credentials = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
        if not _credentials.valid:
            _credentials.refresh(Request())
        return _credentials.token


def _values_url(suffix: str) -> str:
    s = get_settings()
    return (
        f"https://sheets.googleapis.com/v4/spreadsheets/{s.google_sheets_orders_spreadsheet_id}"
        f"/values/{s.google_sheets_orders_tab}{suffix}"
    )


def ensure_header() -> None:
    """Write EXPORT_COLUMNS into row 1 if the tab is empty. Called lazily
    on the first append per process; cheap (one GET)."""
    headers = {"Authorization": f"Bearer {_access_token()}"}
    got = httpx.get(_values_url("!A1:A1"), headers=headers, timeout=_TIMEOUT_SECONDS)
    got.raise_for_status()
    if got.json().get("values"):
        return
    put = httpx.put(
        _values_url("!A1"),
        params={"valueInputOption": "RAW"},
        headers=headers,
        json={"values": [EXPORT_COLUMNS]},
        timeout=_TIMEOUT_SECONDS,
    )
    put.raise_for_status()


_header_checked = False


def append_order_row(row: dict) -> bool:
    """Append one order (an order_export_row dict) as a sheet row, in
    EXPORT_COLUMNS order. Returns True on success, False when unconfigured
    or on any failure. Never raises: this runs after checkout has already
    succeeded and must never affect the customer."""
    global _header_checked
    if not _sheets_configured():
        return False
    try:
        if not _header_checked:
            ensure_header()
            _header_checked = True
        values = [["" if row.get(col) is None else str(row.get(col)) for col in EXPORT_COLUMNS]]
        response = httpx.post(
            _values_url("!A1:append"),
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            headers={"Authorization": f"Bearer {_access_token()}"},
            json={"values": values},
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001 - log and drop, by design
        logger.warning("sheet append for %s failed: %s", row.get("order_number"), exc)
        return False
```

Notes on the snippet:

- `placed_at` is an ISO string; with `USER_ENTERED` Sheets may parse it as
  a date. That is fine. If David wants it left verbatim, switch to `RAW`.
- Row order = `EXPORT_COLUMNS`, so the sheet, the CSV and the webhook all
  line up column for column. `items` is a single cell with lines joined by
  ` | `; the per-line detail is not needed in the sheet.
- The `order_url` from `order_notification_payload` is not in
  `EXPORT_COLUMNS`. If David wants a clickable link column, append
  `"order_url"` to the values list *and* to the header (keep it last so
  the CSV stays unchanged, or add it to `EXPORT_COLUMNS` in one place and
  accept that the CSV grows a column too — preferred).

## Wiring: services/api/app/api/checkout.py

Right after the existing line

```python
background.add_task(order_notify.notify_new_order, payload)
```

add

```python
background.add_task(order_sheet.append_order_row, payload)
```

(`payload` is `order_notification_payload(order, ...)`, which is a
superset of `order_export_row(order)`; `append_order_row` reads only the
`EXPORT_COLUMNS` keys.) Import `order_sheet` alongside `order_notify`.
Both tasks run after the commit; a Sheets outage cannot fail a checkout.

## Optional (v2): update the row when the order is marked paid

Not required for launch. The admin page is the source of truth for status.
If wanted: in `app/services/payments.py::mark_order_paid`, in the manual
branch, enqueue a background call that finds the row whose column A equals
`order.public_order_number` (`values.get` on `Orders!A:A`, then
`values.update` on `C{row}:E{row}` with the new status / payment_status).
Keep it best-effort like everything else here.

## Tests (services/api/tests/test_order_sheet.py)

- Unconfigured (blank spreadsheet id) → `append_order_row(row)` returns
  False and makes no HTTP call.
- Configured → monkeypatch `order_sheet._access_token` to return `"tok"`,
  monkeypatch `httpx.get/put/post` with fakes that record the request;
  assert the append URL contains the spreadsheet id and tab, the header
  is written when A1 is empty and skipped when not, and the values list
  matches `EXPORT_COLUMNS` order for a row built with `order_export_row`
  on a real order (see `tests/test_storefront.py` for how orders are made).
- Google error (fake raises `httpx.HTTPStatusError`) → returns False, logs,
  does not raise.

Run with `.venv/bin/python -m pytest -q` from `services/api`.

## Manual check

1. Put the three env vars in `services/api/.env` (key JSON on one line).
2. Restart the API (`.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`, no `--reload`).
3. Place an order on localhost:3000 (password gate cookies
   `tc_access=1; tc_age_ack=1`; use `test-checkout@example.com`).
4. The sheet gets a header row on the first order and one row per order.
5. Watch the API log for `sheet append for TCP-... failed` if nothing shows
   up; 403 means the sheet is not shared with the service account, 404
   means the spreadsheet id or tab name is wrong.

## Production

Set `GOOGLE_SHEETS_ORDERS_SPREADSHEET_ID`, `GOOGLE_SHEETS_ORDERS_TAB`,
`GOOGLE_SERVICE_ACCOUNT_JSON` on the API host as secrets. Leave
`ORDER_NOTIFY_WEBHOOK_URL` blank unless a second receiver is wanted; both
can run at once.
