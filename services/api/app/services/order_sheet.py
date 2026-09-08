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
