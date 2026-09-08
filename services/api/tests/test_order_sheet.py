"""Tests for the Google Sheets order feed (app/services/order_sheet.py)."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest

from app.models.orders import Order
from app.services import order_sheet
from app.services.order_export import EXPORT_COLUMNS, order_export_row


@pytest.fixture(autouse=True)
def _reset_module_state():
    order_sheet._header_checked = False
    order_sheet._credentials = None
    yield
    order_sheet._header_checked = False
    order_sheet._credentials = None


def _make_order() -> Order:
    return Order(
        created_at=datetime.now(UTC),
        customer_email="sheets-test@example.com",
        public_order_number=f"TCP-{uuid.uuid4().hex[:6].upper()}",
        access_token=uuid.uuid4().hex,
        status="PAYMENT_PENDING",
        currency="usd",
        customer_name="Sheet Tester",
        customer_phone="555-0100",
        shipping_address={"line1": "1 Test Way", "city": "Austin", "region": "TX",
                          "postal_code": "78701", "country": "US"},
        subtotal_cents=12900,
        shipping_cents=0,
        tax_cents=0,
        total_cents=12900,
    )


def test_unconfigured_returns_false_without_http(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_ORDERS_SPREADSHEET_ID", "")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    from app.core.config import get_settings
    get_settings.cache_clear()

    def boom(*args, **kwargs):
        raise AssertionError("no HTTP call expected when unconfigured")

    monkeypatch.setattr(httpx, "get", boom)
    monkeypatch.setattr(httpx, "post", boom)
    assert order_sheet.append_order_row({"order_number": "TCP-X"}) is False
    get_settings.cache_clear()


def test_configured_appends_header_and_row(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_ORDERS_SPREADSHEET_ID", "SHEET123")
    monkeypatch.setenv("GOOGLE_SHEETS_ORDERS_TAB", "Orders")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    from app.core.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setattr(order_sheet, "_access_token", lambda: "tok")

    calls = []

    class FakeResponse:
        def __init__(self, payload=None):
            self._payload = payload or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        calls.append(("get", url, kwargs))
        return FakeResponse()  # empty tab -> header will be written

    def fake_put(url, **kwargs):
        calls.append(("put", url, kwargs))
        return FakeResponse()

    def fake_post(url, **kwargs):
        calls.append(("post", url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "put", fake_put)
    monkeypatch.setattr(httpx, "post", fake_post)

    row = order_export_row(_make_order())
    assert order_sheet.append_order_row(row) is True

    methods = [c[0] for c in calls]
    assert methods == ["get", "put", "post"]
    for _, url, _ in calls:
        assert "SHEET123" in url and "/values/Orders" in url
    # header written RAW, row appended USER_ENTERED
    assert calls[1][2]["params"] == {"valueInputOption": "RAW"}
    assert calls[1][2]["json"]["values"] == [EXPORT_COLUMNS]
    assert calls[2][2]["params"] == {
        "valueInputOption": "USER_ENTERED",
        "insertDataOption": "INSERT_ROWS",
    }
    appended = calls[2][2]["json"]["values"][0]
    assert len(appended) == len(EXPORT_COLUMNS)
    assert appended[EXPORT_COLUMNS.index("order_number")] == row["order_number"]
    assert appended[EXPORT_COLUMNS.index("customer_name")] == "Sheet Tester"

    # second append in the same process skips the header check
    calls.clear()
    assert order_sheet.append_order_row(row) is True
    assert [c[0] for c in calls] == ["post"]
    get_settings.cache_clear()


def test_header_skipped_when_it_already_matches(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_ORDERS_SPREADSHEET_ID", "SHEET123")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setattr(order_sheet, "_access_token", lambda: "tok")

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"values": [list(EXPORT_COLUMNS)]}

    def fake_get(url, **kwargs):
        calls.append(("get", url))
        return FakeResponse()

    def fake_post(url, **kwargs):
        calls.append(("post", url))
        return FakeResponse()

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    assert order_sheet.append_order_row(order_export_row(_make_order())) is True
    assert [c[0] for c in calls] == ["get", "post"]
    get_settings.cache_clear()


def test_google_error_returns_false_and_logs(monkeypatch, caplog):
    monkeypatch.setenv("GOOGLE_SHEETS_ORDERS_SPREADSHEET_ID", "SHEET123")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setattr(order_sheet, "_access_token", lambda: "tok")

    def fake_get(url, **kwargs):
        raise httpx.HTTPStatusError(
            "boom", request=httpx.Request("GET", url), response=httpx.Response(403)
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    with caplog.at_level("WARNING"):
        assert order_sheet.append_order_row({"order_number": "TCP-ERR1"}) is False
    assert any("sheet append for TCP-ERR1 failed" in rec.message for rec in caplog.records)
    get_settings.cache_clear()


def test_export_row_carries_discount_code_beside_the_order_number():
    order = _make_order()
    assert order_export_row(order)["discount_code"] == ""
    order.discount_code = "NATALIE"
    order.discount_cents = 1290
    assert order_export_row(order)["discount_code"] == "NATALIE"
    assert EXPORT_COLUMNS[:3] == ["order_number", "discount_code", "placed_at"]
    assert "discount" not in EXPORT_COLUMNS  # the amount is already in total


def test_header_is_rewritten_when_columns_were_appended(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_ORDERS_SPREADSHEET_ID", "SHEET123")
    monkeypatch.setenv("GOOGLE_SHEETS_ORDERS_TAB", "Orders")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setattr(order_sheet, "_access_token", lambda: "tok")

    calls = []

    class FakeResponse:
        def __init__(self, payload=None):
            self._payload = payload or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    # A header that is missing a column gets rewritten in place.
    old_header = [c for c in EXPORT_COLUMNS if c != "discount_code"]
    monkeypatch.setattr(httpx, "get", lambda url, **kw: FakeResponse({"values": [old_header]}))
    monkeypatch.setattr(httpx, "put", lambda url, **kw: calls.append(("put", kw)) or FakeResponse())
    monkeypatch.setattr(httpx, "post", lambda url, **kw: calls.append(("post", kw)) or FakeResponse())

    assert order_sheet.append_order_row(order_export_row(_make_order())) is True
    assert [c[0] for c in calls] == ["put", "post"]
    assert calls[0][1]["json"]["values"] == [EXPORT_COLUMNS]
