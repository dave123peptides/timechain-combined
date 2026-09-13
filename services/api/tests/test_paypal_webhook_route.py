"""End-to-end through the HTTP layer: a PayPal webhook through POST
/api/v1/webhooks/payments/paypal and the customer's return through POST
/shop/orders/{token}/paypal/capture, with the real provider, real DB and
the route's idempotency guard (app/api/webhooks.py). PayPal itself is a
scripted fake (signature verification, order lookup, capture)."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.orders import Order
from app.models.payments import Payment
from app.payments import paypal
from app.services import order_paid

_TEST_EMAIL = "paypal-route-test@example.invalid"
_PP_ORDER_ID = "7A123456BB789012C"
_CAPTURE_ID = "9D876543EE210987F"
_WEBHOOK_URL = "/api/v1/webhooks/payments/paypal"
_HEADERS = {
    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
    "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-1",
    "PAYPAL-TRANSMISSION-ID": "route-test-transmission",
    "PAYPAL-TRANSMISSION-SIG": "sig",
    "PAYPAL-TRANSMISSION-TIME": "2026-09-13T05:00:00Z",
    "Content-Type": "application/json",
}


def _cleanup(session):
    session.execute(text("DELETE FROM webhook_events WHERE source = 'paypal' AND external_id LIKE 'WH-ROUTE-%'"))
    rows = session.execute(text("SELECT id FROM orders WHERE customer_email = :email"), {"email": _TEST_EMAIL}).fetchall()
    if rows:
        ids = [r[0] for r in rows]
        session.execute(
            text("DELETE FROM payment_events WHERE payment_id IN (SELECT id FROM payments WHERE order_id = ANY(:ids))"),
            {"ids": ids},
        )
        session.execute(text("DELETE FROM payments WHERE order_id = ANY(:ids)"), {"ids": ids})
        session.execute(text("DELETE FROM order_events WHERE order_id = ANY(:ids)"), {"ids": ids})
        session.execute(text("DELETE FROM orders WHERE id = ANY(:ids)"), {"ids": ids})
    session.execute(text("DELETE FROM payments WHERE provider_payment_id = :pid"), {"pid": _PP_ORDER_ID})
    session.commit()


@pytest.fixture
def session():
    db = SessionLocal()
    _cleanup(db)
    yield db
    db.rollback()
    _cleanup(db)
    db.close()


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "paypal_client_id", "test-client-id")
    monkeypatch.setattr(settings, "paypal_client_secret", "test-client-secret")
    monkeypatch.setattr(settings, "paypal_environment", "sandbox")
    monkeypatch.setattr(settings, "paypal_webhook_id", "WH-ID-ROUTE-TEST")
    monkeypatch.setattr(settings, "fulfillment_mode", "manual")
    monkeypatch.setattr(paypal, "_access_token", lambda: "test-token")
    paypal._reset_token_cache()


@pytest.fixture
def fanout_calls(monkeypatch):
    calls: list[uuid.UUID] = []
    monkeypatch.setattr(order_paid, "run_order_paid_fanout", lambda order_id: calls.append(order_id))
    return calls


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _FakePayPal:
    def __init__(self, *, verify="SUCCESS", order_status="COMPLETED", capture_status="COMPLETED", value="129.00", lookup_raises=None, capture_issue=None):
        self.verify = verify
        self.order_status = order_status
        self.capture_status = capture_status
        self.value = value
        self.lookup_raises = lookup_raises
        self.capture_issue = capture_issue
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return None

    def _order(self):
        return {
            "id": _PP_ORDER_ID,
            "status": self.order_status,
            "purchase_units": [
                {"payments": {"captures": [{"id": _CAPTURE_ID, "status": self.capture_status, "amount": {"currency_code": "USD", "value": self.value}}]}}
            ],
        }

    def post(self, url, **kwargs):
        self.calls.append(f"POST {url}")
        if url.endswith("/verify-webhook-signature"):
            return _Response(200, {"verification_status": self.verify})
        if url.endswith("/capture"):
            if self.capture_issue:
                return _Response(422, {"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": self.capture_issue}]})
            return _Response(201, self._order())
        raise AssertionError(f"unexpected POST {url}")

    def get(self, url, **kwargs):
        self.calls.append(f"GET {url}")
        if self.lookup_raises:
            raise self.lookup_raises
        if url.endswith(f"/v2/checkout/orders/{_PP_ORDER_ID}"):
            return _Response(200, self._order())
        raise AssertionError(f"unexpected GET {url}")


def _install(monkeypatch, **kwargs) -> _FakePayPal:
    fake = _FakePayPal(**kwargs)
    monkeypatch.setattr(paypal, "_client", lambda: fake)
    return fake


def _make_order(session, *, provider="paypal") -> Order:
    order = Order(
        customer_email=_TEST_EMAIL,
        public_order_number=f"PEN-{uuid.uuid4().hex[:6].upper()}",
        access_token=uuid.uuid4().hex,
        status="PAYMENT_PENDING",
        subtotal_cents=12900,
        shipping_cents=0,
        tax_cents=0,
        total_cents=12900,
    )
    session.add(order)
    session.flush()
    session.add(
        Payment(
            order_id=order.id,
            provider=provider,
            provider_payment_id=_PP_ORDER_ID if provider == "paypal" else None,
            status="pending",
            amount_cents=12900,
            currency="usd",
            provider_data={"provider_payment_id": _PP_ORDER_ID, "approve_url": "https://www.sandbox.paypal.com/checkoutnow?token=x"} if provider == "paypal" else None,
        )
    )
    session.commit()
    return order


def _body(order: Order, event_id="WH-ROUTE-1", value="129.00") -> bytes:
    return json.dumps(
        {
            "id": event_id,
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource_type": "capture",
            "resource": {
                "id": _CAPTURE_ID,
                "status": "COMPLETED",
                "amount": {"currency_code": "USD", "value": value},
                "custom_id": order.public_order_number,
                "supplementary_data": {"related_ids": {"order_id": _PP_ORDER_ID}},
            },
        }
    ).encode()


def _webhook_rows(session) -> int:
    return session.execute(
        text("SELECT count(*) FROM webhook_events WHERE source = 'paypal' AND external_id LIKE 'WH-ROUTE-%'")
    ).scalar_one()


# --- webhook route -----------------------------------------------------------


def test_signed_capture_webhook_marks_order_paid_and_schedules_fanout(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    fake = _install(monkeypatch)
    client = TestClient(app)

    response = client.post(_WEBHOOK_URL, content=_body(order), headers=_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    session.expire_all()
    assert session.get(Order, order.id).status == "PAID"
    assert fanout_calls == [order.id]
    assert _webhook_rows(session) == 1
    assert fake.calls == [
        "POST https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature",
        f"GET https://api-m.sandbox.paypal.com/v2/checkout/orders/{_PP_ORDER_ID}",
    ]


def test_duplicate_delivery_returns_already_processed(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    _install(monkeypatch)
    client = TestClient(app)

    first = client.post(_WEBHOOK_URL, content=_body(order), headers=_HEADERS)
    second = client.post(_WEBHOOK_URL, content=_body(order), headers=_HEADERS)

    assert first.json() == {"status": "processed"}
    assert second.status_code == 200
    assert second.json() == {"status": "already_processed"}
    assert fanout_calls == [order.id]
    assert _webhook_rows(session) == 1
    confirmed = session.execute(
        text(
            "SELECT count(*) FROM payment_events WHERE event_type = 'payment.confirmed' "
            "AND payment_id IN (SELECT id FROM payments WHERE order_id = :oid)"
        ),
        {"oid": order.id},
    ).scalar_one()
    assert confirmed == 1


def test_forged_signature_returns_400_and_writes_nothing(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    fake = _install(monkeypatch, verify="FAILURE")
    client = TestClient(app)

    response = client.post(_WEBHOOK_URL, content=_body(order), headers=_HEADERS)

    assert response.status_code == 400
    assert "verification failed" in response.json()["detail"].lower()
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert _webhook_rows(session) == 0
    assert fanout_calls == []
    assert len(fake.calls) == 1  # verify only; never looked the order up


def test_missing_signature_headers_return_400_without_calling_paypal(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    _install(monkeypatch)
    client = TestClient(app)
    response = client.post(_WEBHOOK_URL, content=_body(order), headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert _webhook_rows(session) == 0
    assert fanout_calls == []


def test_blank_webhook_id_rejects_every_webhook(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    _install(monkeypatch)
    monkeypatch.setattr(get_settings(), "paypal_webhook_id", "")
    client = TestClient(app)
    response = client.post(_WEBHOOK_URL, content=_body(order), headers=_HEADERS)
    assert response.status_code == 400
    assert _webhook_rows(session) == 0


def test_unknown_order_is_acknowledged_and_ignored(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    _install(monkeypatch)
    client = TestClient(app)
    body = json.loads(_body(order, event_id="WH-ROUTE-unknown"))
    body["resource"]["supplementary_data"]["related_ids"]["order_id"] = "NOPE0000000000001"
    response = client.post(_WEBHOOK_URL, content=json.dumps(body).encode(), headers=_HEADERS)
    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert fanout_calls == []


def test_paid_when_refetch_fails_returns_500_and_commits_nothing(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    _install(monkeypatch, lookup_raises=httpx.ConnectError("boom"))
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(_WEBHOOK_URL, content=_body(order), headers=_HEADERS)

    assert response.status_code == 500
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert _webhook_rows(session) == 0  # so PayPal's retry gets a clean attempt
    assert fanout_calls == []


def test_paid_when_paypal_disagrees_returns_500_and_commits_nothing(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    _install(monkeypatch, order_status="APPROVED", capture_status="PENDING")
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(_WEBHOOK_URL, content=_body(order), headers=_HEADERS)
    assert response.status_code == 500
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert _webhook_rows(session) == 0


def test_amount_mismatch_is_recorded_and_acknowledged_without_paying(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    _install(monkeypatch, value="12.90")
    client = TestClient(app)
    response = client.post(_WEBHOOK_URL, content=_body(order, value="12.90"), headers=_HEADERS)
    assert response.status_code == 200
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert fanout_calls == []
    mismatch = session.execute(
        text("SELECT count(*) FROM order_events WHERE order_id = :oid AND event_type = 'payment_amount_mismatch'"),
        {"oid": order.id},
    ).scalar_one()
    assert mismatch == 1


# --- the customer's return -----------------------------------------------------


def _capture_url(order: Order) -> str:
    return f"/shop/orders/{order.access_token}/paypal/capture"


def test_return_capture_marks_order_paid_and_schedules_fanout(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    fake = _install(monkeypatch)
    client = TestClient(app)

    response = client.post(_capture_url(order))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PAID"
    assert body["payment_method"] == "paypal"
    assert body["payment_status"] == "succeeded"
    assert body["payment_details"] is None
    session.expire_all()
    assert session.get(Order, order.id).status == "PAID"
    assert fanout_calls == [order.id]
    assert fake.calls == [f"POST https://api-m.sandbox.paypal.com/v2/checkout/orders/{_PP_ORDER_ID}/capture"]


def test_return_capture_then_webhook_is_idempotent(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    _install(monkeypatch)
    client = TestClient(app)

    assert client.post(_capture_url(order)).json()["status"] == "PAID"
    webhook = client.post(_WEBHOOK_URL, content=_body(order), headers=_HEADERS)

    assert webhook.status_code == 200
    assert fanout_calls == [order.id]  # once
    confirmed = session.execute(
        text(
            "SELECT count(*) FROM payment_events WHERE event_type = 'payment.confirmed' "
            "AND payment_id IN (SELECT id FROM payments WHERE order_id = :oid)"
        ),
        {"oid": order.id},
    ).scalar_one()
    assert confirmed == 1


def test_return_capture_after_webhook_returns_the_paid_order_without_paypal(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    fake = _install(monkeypatch)
    client = TestClient(app)
    assert client.post(_WEBHOOK_URL, content=_body(order), headers=_HEADERS).status_code == 200
    calls_before = len(fake.calls)

    response = client.post(_capture_url(order))

    assert response.status_code == 200
    assert response.json()["status"] == "PAID"
    assert len(fake.calls) == calls_before
    assert fanout_calls == [order.id]


def test_return_capture_not_approved_returns_409(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    _install(monkeypatch, capture_issue="ORDER_NOT_APPROVED")
    client = TestClient(app)
    response = client.post(_capture_url(order))
    assert response.status_code == 409
    assert "not completed" in response.json()["detail"].lower()
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert fanout_calls == []


def test_return_capture_paypal_failure_returns_400(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    _install(monkeypatch, capture_issue="INSTRUMENT_DECLINED")
    client = TestClient(app)
    response = client.post(_capture_url(order))
    assert response.status_code == 400
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"


def test_return_capture_refuses_non_paypal_orders(session, monkeypatch, fanout_calls):
    order = _make_order(session, provider="zelle")
    _install(monkeypatch)
    client = TestClient(app)
    response = client.post(_capture_url(order))
    assert response.status_code == 400
    assert "paypal" in response.json()["detail"].lower()


def test_return_capture_unknown_token_is_404(monkeypatch):
    _install(monkeypatch)
    assert TestClient(app).post("/shop/orders/not-a-token/paypal/capture").status_code == 404


# --- the checkout gate -----------------------------------------------------------


def test_checkout_refuses_paypal_while_switched_off(monkeypatch):
    monkeypatch.setattr(get_settings(), "paypal_checkout_enabled", False)
    client = TestClient(app)
    response = client.post(
        "/api/v1/checkout/create",
        json={
            "email": "paypal-gate-test@example.com",
            "customer_name": "Pay Pal",
            "customer_phone": "3055550100",
            "shipping_address": {"line1": "1 Main St", "line2": None, "city": "Miami", "region": "FL", "postal_code": "33101", "country": "US"},
            "items": [{"variant_id": str(uuid.uuid4()), "quantity": 1}],
            "consent": {"age_confirmed": True, "ruo_acknowledged": True, "terms_accepted": True},
            "payment_method": "paypal",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "PayPal checkout is not available right now. Please choose another payment method."


def test_retry_payment_refuses_paypal_while_switched_off(session, monkeypatch):
    order = _make_order(session)
    monkeypatch.setattr(get_settings(), "paypal_checkout_enabled", False)
    response = TestClient(app).post(f"/shop/orders/{order.access_token}/retry-payment")
    assert response.status_code == 400
    assert "paypal" in response.json()["detail"].lower()
