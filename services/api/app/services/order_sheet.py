"""Append each new order to a Google Sheet via a service account."""

from __future__ import annotations

import json
import logging
import threading

import httpx
from google.auth import transport as auth_transport
from google.oauth2 import credentials as google_auth_credentials
from google.oauth2 import service_account

from app.core.config import get_settings
from app.services.order_export import EXPORT_COLUMNS

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_TIMEOUT_SECONDS = 10.0
_lock = threading.Lock()
_credentials = None  # cached; google-auth refreshes the token itself


class _HttpxAuthResponse(auth_transport.Response):
    """Adapts an httpx response to what google-auth's refresh expects."""

    def __init__(self, response: httpx.Response):
        self._response = response

    @property
    def status(self) -> int:
        return self._response.status_code

    @property
    def headers(self):
        return dict(self._response.headers)

    @property
    def data(self) -> bytes:
        return self._response.content


class _HttpxAuthRequest(auth_transport.Request):
    """Token refresh over httpx — the API's existing HTTP client — so the
    only added dependency is google-auth itself (no `requests`)."""

    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        response = httpx.request(
            method, url, content=body, headers=headers, timeout=timeout, **kwargs
        )
        return _HttpxAuthResponse(response)


def _sheets_configured() -> bool:
    s = get_settings()
    return bool(
        s.google_sheets_orders_spreadsheet_id.strip()
        and (s.google_service_account_json.strip() or s.google_sheets_refresh_token_json.strip())
    )


def _access_token() -> str:
    global _credentials
    with _lock:
        s = get_settings()
        if s.google_service_account_json.strip():
            if _credentials is None:
                info = json.loads(s.google_service_account_json)
                _credentials = service_account.Credentials.from_service_account_info(
                    info, scopes=_SCOPES
                )
            if not _credentials.valid:
                _credentials.refresh(_HttpxAuthRequest())
            return _credentials.token
        # OAuth refresh-token mode (Workspaces that block SA keys).
        if _credentials is None:
            info = json.loads(s.google_sheets_refresh_token_json)
            _credentials = google_auth_credentials.Credentials(
                None,
                refresh_token=info["refresh_token"],
                token_uri=info["token_uri"],
                client_id=info["client_id"],
                client_secret=info["client_secret"],
                scopes=_SCOPES,
            )
        if not _credentials.valid:
            _credentials.refresh(_HttpxAuthRequest())
        return _credentials.token


def _values_url(suffix: str) -> str:
    s = get_settings()
    return (
        f"https://sheets.googleapis.com/v4/spreadsheets/{s.google_sheets_orders_spreadsheet_id}"
        f"/values/{s.google_sheets_orders_tab}{suffix}"
    )


def ensure_header() -> None:
    """Write EXPORT_COLUMNS into row 1 if the tab is empty, or rewrite
    row 1 when it no longer matches. Rewriting row 1 never moves data,
    so this is only right for columns appended to the end of
    EXPORT_COLUMNS; a column inserted in the middle (discount_code, 9/6)
    must be inserted in the sheet itself first, after which row 1 already
    matches and this is a no-op. Called lazily on the first append per
    process; cheap (one GET)."""
    headers = {"Authorization": f"Bearer {_access_token()}"}
    got = httpx.get(_values_url("!1:1"), headers=headers, timeout=_TIMEOUT_SECONDS)
    got.raise_for_status()
    current = (got.json().get("values") or [[]])[0]
    if current == EXPORT_COLUMNS:
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


def _ensure_header_once() -> None:
    """ensure_header(), at most once per process (cheap: one GET)."""
    global _header_checked
    if not _header_checked:
        ensure_header()
        _header_checked = True


def _row_values(row: dict) -> list[str]:
    return ["" if row.get(col) is None else str(row.get(col)) for col in EXPORT_COLUMNS]


def _column_letter(n: int) -> str:
    """1 → A, 22 → V, 26 → Z, 27 → AA."""
    letters = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def append_order_row(row: dict) -> bool:
    """Append one order (an order_export_row dict) as a sheet row, in
    EXPORT_COLUMNS order. Returns True on success, False when unconfigured
    or on any failure. Never raises: this runs after checkout has already
    succeeded and must never affect the customer."""
    if not _sheets_configured():
        return False
    try:
        _ensure_header_once()
        values = [_row_values(row)]
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


def update_order_row(row: dict) -> bool:
    """Rewrite the sheet row for `row["order_number"]` in place (columns
    A..<last EXPORT_COLUMNS column> only, so notes typed to the right of
    the data survive), or append it when no such row exists. Used once
    an order is PAID so the row's status / payment_status /
    payment_method flip without ever creating a second row for the same
    order (David, 9/10). Column A is scanned top to bottom, skipping the
    header; TCP- rows from the vial site share the tab and simply never
    match. Appends never shift existing rows, so the index read here
    stays valid even if another order is appended meanwhile. Returns
    True on success, False when unconfigured or on any failure. Never
    raises."""
    order_number = row.get("order_number")
    if not _sheets_configured():
        return False
    try:
        _ensure_header_once()
        headers = {"Authorization": f"Bearer {_access_token()}"}
        got = httpx.get(_values_url("!A:A"), headers=headers, timeout=_TIMEOUT_SECONDS)
        got.raise_for_status()
        column_a = got.json().get("values") or []
        row_number = next(
            (
                index + 1
                for index, cells in enumerate(column_a)
                if index > 0 and cells and cells[0] == order_number
            ),
            None,
        )
        if row_number is None:
            logger.info("sheet row for %s not found; appending instead", order_number)
            return append_order_row(row)
        last_column = _column_letter(len(EXPORT_COLUMNS))
        put = httpx.put(
            _values_url(f"!A{row_number}:{last_column}{row_number}"),
            params={"valueInputOption": "USER_ENTERED"},
            headers=headers,
            json={"values": [_row_values(row)]},
            timeout=_TIMEOUT_SECONDS,
        )
        put.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001 - log and drop, by design
        logger.warning("sheet update for %s failed: %s", order_number, exc)
        return False
