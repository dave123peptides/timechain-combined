"""WHOP_CHECKOUT_ENABLED (app/api/checkout.py): off in production until
David has tested a live card order (9/14). Mirrors the PayPal gate
tests in test_paypal_webhook_route.py."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.checkout import BITCOIN_UNAVAILABLE, WHOP_UNAVAILABLE
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.orders import Order
from app.models.payments import Payment
from app.services import storefront

_TEST_EMAIL = "whop-flag-test@example.com"

_CREATE_BODY = {
    "email": _TEST_EMAIL,
    "customer_name": "Flag Test",
    "customer_phone": "555-0100",
    "shipping_address": {"line1": "1 Test St", "line2": None, "city": "Testville", "region": "CA", "postal_code": "90210", "country": "US"},
    "items": [{"variant_id": str(uuid.uuid4()), "quantity": 1}],
    "consent": {"age_confirmed": True, "ruo_acknowledged": True, "terms_accepted": True},
    "payment_method": "whop",
}


def _cleanup(session):
    rows = session.execute(text("SELECT id FROM orders WHERE customer_email = :email"), {"email": _TEST_EMAIL}).fetchall()
    if rows:
        ids = [r[0] for r in rows]
        session.execute(text("DELETE FROM payments WHERE order_id = ANY(:ids)"), {"ids": ids})
        session.execute(text("DELETE FROM order_events WHERE order_id = ANY(:ids)"), {"ids": ids})
        session.execute(text("DELETE FROM orders WHERE id = ANY(:ids)"), {"ids": ids})
    session.commit()


@pytest.fixture
def session():
    db = SessionLocal()
    _cleanup(db)
    yield db
    db.rollback()
    _cleanup(db)
    db.close()


@pytest.fixture
def sentinel_create(monkeypatch):
    """Replace create_order so a request that passes the switch fails
    with a recognisable StorefrontError instead of needing a catalog."""

    def boom(*args, **kwargs):
        raise storefront.StorefrontError("sentinel: past the switch")

    monkeypatch.setattr(storefront, "create_order", boom)


def _pending_whop_order(session, payment_status: str = "pending") -> Order:
    order = Order(
        customer_email=_TEST_EMAIL,
        public_order_number=f"PEN-{uuid.uuid4().hex[:6].upper()}",
        access_token=uuid.uuid4().hex,
        status="PAYMENT_PENDING",
        subtotal_cents=1200,
        shipping_cents=4000,
        tax_cents=0,
        total_cents=5200,
    )
    session.add(order)
    session.flush()
    session.add(Payment(order_id=order.id, provider="whop", status=payment_status, amount_cents=5200, currency="usd"))
    session.commit()
    return order


def test_whop_order_refused_when_switch_off(monkeypatch, sentinel_create):
    monkeypatch.setattr(get_settings(), "whop_checkout_enabled", False)
    response = TestClient(app).post("/api/v1/checkout/create", json=_CREATE_BODY)
    assert response.status_code == 400
    assert response.json()["detail"] == WHOP_UNAVAILABLE


def test_whop_order_passes_switch_when_on(monkeypatch, sentinel_create):
    monkeypatch.setattr(get_settings(), "whop_checkout_enabled", True)
    response = TestClient(app).post("/api/v1/checkout/create", json=_CREATE_BODY)
    assert response.status_code == 400
    assert response.json()["detail"] == "sentinel: past the switch"


def test_manual_transfer_orders_ignore_the_switch(monkeypatch, sentinel_create):
    monkeypatch.setattr(get_settings(), "whop_checkout_enabled", False)
    response = TestClient(app).post("/api/v1/checkout/create", json={**_CREATE_BODY, "payment_method": "zelle"})
    assert response.status_code == 400
    assert response.json()["detail"] == "sentinel: past the switch"


def test_bitcoin_switch_does_not_gate_whop(monkeypatch, sentinel_create):
    monkeypatch.setattr(get_settings(), "bitcoin_checkout_enabled", False)
    monkeypatch.setattr(get_settings(), "whop_checkout_enabled", True)
    response = TestClient(app).post("/api/v1/checkout/create", json=_CREATE_BODY)
    assert response.json()["detail"] == "sentinel: past the switch"
    # ... and the Bitcoin switch still guards Bitcoin with its own message.
    bitcoin = TestClient(app).post("/api/v1/checkout/create", json={**_CREATE_BODY, "payment_method": "bitcoin_opennode"})
    assert bitcoin.json()["detail"] == BITCOIN_UNAVAILABLE


def test_retry_payment_refused_when_switch_off(session, monkeypatch):
    monkeypatch.setattr(get_settings(), "whop_checkout_enabled", False)
    order = _pending_whop_order(session)
    response = TestClient(app).post(f"/shop/orders/{order.access_token}/retry-payment")
    assert response.status_code == 400
    assert response.json()["detail"] == WHOP_UNAVAILABLE


def test_retry_payment_when_on_reaches_recreate(session, monkeypatch):
    """Past the switch, with no API key configured, the re-mint degrades
    with the storefront's generic message rather than the switch's."""
    monkeypatch.setattr(get_settings(), "whop_checkout_enabled", True)
    monkeypatch.setattr(get_settings(), "whop_api_key", "")
    order = _pending_whop_order(session)
    response = TestClient(app).post(f"/shop/orders/{order.access_token}/retry-payment")
    assert response.status_code == 400
    assert response.json()["detail"] == "This payment method is not available right now. Please try again later."
