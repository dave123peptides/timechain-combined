"""Tests for the GoHighLevel CRM push (app/services/ghl_notify.py)."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest

from app.models.orders import Order
from app.services import ghl_notify


def _row(**overrides) -> dict:
    row = {
        "order_number": f"PEN-{uuid.uuid4().hex[:6].upper()}",
        "customer_name": "G H L Test",
        "customer_phone": "+1 305 555 0100",
        "customer_email": "ghl-test@example.com",
        "payment_method": "venmo",
        "total": "129.00",
        "currency": "usd",
        "order_url": "https://buytcp.com/order/tok",
    }
    row.update(overrides)
    return row


def test_payload_is_customer_safe():
    """The payload carries only what the customer may see — no items,
    no supplier data (compliance: emails stay peptide-free)."""
    row = _row()
    row["items"] = "2 x BPC-157 [supplier: BPC-10]"
    row["items_detail"] = [{"name": "BPC-157", "supplier_sku": "BPC-10"}]
    payload = ghl_notify.ghl_payload(row)
    assert payload is not None
    assert payload == {
        "email": "ghl-test@example.com",
        "first_name": "G",
        "last_name": "H L Test",
        "name": "G H L Test",
        "phone": "+1 305 555 0100",
        "order_number": row["order_number"],
        "payment_method": "venmo",
        "total": "129.00",
        "currency": "USD",
        "order_url": "https://buytcp.com/order/tok",
        "event": "order.created",
        "order_status": "",
        "payment_method_label": "Venmo",
        "pay_url": "https://buytcp.com/order/tok",
    }
    assert "items" not in payload
    assert "supplier" not in str(payload).lower()


def test_payload_skips_order_without_email():
    assert ghl_notify.ghl_payload(_row(customer_email="")) is None
    assert ghl_notify.ghl_payload(_row(customer_email="  ")) is None


def test_payload_handles_missing_fields():
    payload = ghl_notify.ghl_payload({"order_number": "PEN-1"})
    assert payload is None  # no email
    payload = ghl_notify.ghl_payload({"order_number": "PEN-1", "customer_email": "a@b.co"})
    assert payload is not None
    assert payload["first_name"] == ""
    assert payload["order_url"] == ""


def test_push_unconfigured_returns_false_without_http(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ghl_order_webhook_url", "")

    def boom(*args, **kwargs):
        raise AssertionError("no HTTP call expected when unconfigured")

    monkeypatch.setattr(httpx, "post", boom)
    payload = ghl_notify.ghl_payload(_row())
    assert payload is not None
    assert ghl_notify.push_order_to_ghl(payload) is False


def test_push_posts_to_configured_url(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ghl_order_webhook_url", "https://webhooks.leadconnectorhq.com/wf/example")

    captured = {}

    class _Response:
        status_code = 200

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Response()

    monkeypatch.setattr(httpx, "post", fake_post)
    payload = ghl_notify.ghl_payload(_row())
    assert payload is not None
    assert ghl_notify.push_order_to_ghl(payload) is True
    assert captured["url"] == "https://webhooks.leadconnectorhq.com/wf/example"
    assert captured["json"]["email"] == "ghl-test@example.com"
    assert captured["json"]["order_number"] == payload["order_number"]


def test_push_swallows_http_failure(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ghl_order_webhook_url", "https://webhooks.example.invalid/wf")

    def fake_post(url, json=None, timeout=None):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "post", fake_post)
    payload = ghl_notify.ghl_payload(_row())
    assert payload is not None
    assert ghl_notify.push_order_to_ghl(payload) is False


def test_push_false_on_non_2xx(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ghl_order_webhook_url", "https://webhooks.example.invalid/wf")

    class _Response:
        status_code = 403

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Response())
    payload = ghl_notify.ghl_payload(_row())
    assert payload is not None
    assert ghl_notify.push_order_to_ghl(payload) is False
