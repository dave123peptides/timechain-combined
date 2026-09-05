from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid

import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.orders import Order
from app.models.payments import Payment
from app.payments.base import VerifiedEvent
from app.payments.speed import (
    SpeedError,
    SpeedNotConfigured,
    SpeedProvider,
    compute_expected_signature,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_TEST_EMAIL = "speed-provider-test@example.invalid"
_TEST_SESSION_ID = "cs_test_speed_provider_000000000001"

# A valid Base64 payload for the wsec_ secret. The Base64-decoded bytes are
# the HMAC key.
_SECRET_PLAIN = "test-secret-key-for-speed-webhook"
_SECRET_B64 = base64.b64encode(_SECRET_PLAIN.encode()).decode()
_TEST_SECRET = f"wsec_{_SECRET_B64}"


def _cleanup(session):
    rows = session.execute(
        text("SELECT id FROM orders WHERE customer_email = :email"), {"email": _TEST_EMAIL}
    ).fetchall()
    if rows:
        order_ids = [r[0] for r in rows]
        session.execute(
            text("DELETE FROM payment_events WHERE payment_id IN (SELECT id FROM payments WHERE order_id = ANY(:ids))"),
            {"ids": order_ids},
        )
        session.execute(
            text("DELETE FROM payments WHERE order_id = ANY(:ids)"), {"ids": order_ids}
        )
        session.execute(
            text("DELETE FROM order_events WHERE order_id = ANY(:ids)"), {"ids": order_ids}
        )
        session.execute(
            text("DELETE FROM order_items WHERE order_id = ANY(:ids)"), {"ids": order_ids}
        )
        session.execute(text("DELETE FROM orders WHERE id = ANY(:ids)"), {"ids": order_ids})
    session.execute(
        text("DELETE FROM payments WHERE provider_payment_id = :pid"),
        {"pid": _TEST_SESSION_ID},
    )
    session.commit()


@pytest.fixture
def db():
    session = SessionLocal()
    _cleanup(session)
    yield session
    session.rollback()
    _cleanup(session)
    session.close()


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    """Give every test a configured Speed key + secret so the provider
    doesn't raise SpeedNotConfigured unless the test explicitly clears
    the values."""
    settings = get_settings()
    monkeypatch.setattr(settings, "speed_api_key", "sk_test_unit_test_key")
    monkeypatch.setattr(settings, "speed_webhook_secret", _TEST_SECRET)
    monkeypatch.setattr(settings, "public_site_url", "http://localhost:3010")


def _sign(msg_id: str, timestamp: str, body: bytes, secret: str = _TEST_SECRET) -> str:
    """Produce the exact v1,<sig> string a real Speed delivery carries."""
    key = base64.b64decode(secret[len("wsec_"):])
    payload = f"{msg_id}.{timestamp}.".encode() + body
    sig = base64.b64encode(hmac.new(key, payload, hashlib.sha256).digest()).decode()
    return f"v1,{sig}"


def _paid_event_body(session_id: str, amount: float, currency: str = "USD") -> dict:
    return {
        "id": f"evt_{session_id}",
        "api_version": "2022-10-15",
        "event_type": "checkout_session.paid",
        "object": "events",
        "livemode": False,
        "data": {
            "object": {
                "id": session_id,
                "object": "checkout_session",
                "status": "paid",
                "currency": currency,
                "amount": amount,
                "payments": [],
            }
        },
    }


def _make_order_and_payment(db, *, total_cents: int = 12900) -> tuple[Order, Payment]:
    order = Order(
        customer_email=_TEST_EMAIL,
        public_order_number=f"TC-SPEED-{uuid.uuid4().hex[:8].upper()}",
        access_token=uuid.uuid4().hex,
        status="PAYMENT_PENDING",
        subtotal_cents=total_cents,
        shipping_cents=0,
        tax_cents=0,
        total_cents=total_cents,
    )
    db.add(order)
    db.flush()
    payment = Payment(
        order_id=order.id,
        provider="crypto",
        provider_payment_id=_TEST_SESSION_ID,
        status="pending",
        amount_cents=total_cents,
        currency="usd",
    )
    db.add(payment)
    db.flush()
    return order, payment


# ---------------------------------------------------------------------------
# compute_expected_signature
# ---------------------------------------------------------------------------


class TestComputeExpectedSignature:
    def test_produces_matching_hmac(self):
        msg_id = "msg_test_001"
        ts = "1700000000"
        body = b'{"hello":"world"}'
        sig = compute_expected_signature(_TEST_SECRET, msg_id, ts, body)
        # Recompute independently to confirm determinism.
        key = base64.b64decode(_SECRET_B64)
        expected = base64.b64encode(
            hmac.new(key, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()
        ).decode()
        assert sig == expected

    def test_rejects_secret_without_prefix(self):
        with pytest.raises(SpeedError, match="wsec_"):
            compute_expected_signature("no-prefix", "id", "ts", b"body")

    def test_rejects_invalid_base64(self):
        with pytest.raises(SpeedError, match="Base64"):
            compute_expected_signature("wsec_!!!not-base64!!!", "id", "ts", b"body")


# ---------------------------------------------------------------------------
# verify_webhook
# ---------------------------------------------------------------------------


class TestVerifyWebhook:
    def _headers(self, body: bytes, msg_id: str = "msg_test_verify", ts: str = "1700000000"):
        return {
            "webhook-signature": _sign(msg_id, ts, body),
            "webhook-timestamp": ts,
            "webhook-id": msg_id,
        }

    def test_valid_signature_returns_event(self):
        body = json.dumps(_paid_event_body(_TEST_SESSION_ID, 129.00)).encode()
        provider = SpeedProvider()
        event = provider.verify_webhook(self._headers(body), body)
        assert event.event_type == "checkout_session.paid"
        assert event.external_id == f"evt_{_TEST_SESSION_ID}"

    def test_wrong_signature_raises(self):
        body = json.dumps(_paid_event_body(_TEST_SESSION_ID, 129.00)).encode()
        headers = self._headers(body)
        headers["webhook-signature"] = "v1,wrongsignature=="
        provider = SpeedProvider()
        with pytest.raises(SpeedError, match="signature does not match"):
            provider.verify_webhook(headers, body)

    def test_missing_headers_raises(self):
        body = b"{}"
        provider = SpeedProvider()
        with pytest.raises(SpeedError, match="Missing"):
            provider.verify_webhook({"webhook-id": "x"}, body)

    def test_multiple_signatures_accepts_any_match(self):
        body = json.dumps(_paid_event_body(_TEST_SESSION_ID, 129.00)).encode()
        good = _sign("msg_m", "1700000000", body)
        headers = {
            "webhook-signature": f"v1,bogus== {good}",
            "webhook-timestamp": "1700000000",
            "webhook-id": "msg_m",
        }
        provider = SpeedProvider()
        event = provider.verify_webhook(headers, body)
        assert event.event_type == "checkout_session.paid"

    def test_no_key_configured_raises(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "speed_webhook_secret", "")
        provider = SpeedProvider()
        with pytest.raises(SpeedNotConfigured):
            provider.verify_webhook({"webhook-id": "x"}, b"{}")


# ---------------------------------------------------------------------------
# handle_event
# ---------------------------------------------------------------------------


class TestHandleEvent:
    def _verified(self, body: dict) -> VerifiedEvent:
        return VerifiedEvent(
            external_id=body["id"],
            event_type=body["event_type"],
            order_id=None,
            raw=body,
        )

    def test_paid_marks_order_paid(self, db):
        order, payment = _make_order_and_payment(db)
        body = _paid_event_body(_TEST_SESSION_ID, order.total_cents / 100)
        provider = SpeedProvider()
        provider.handle_event(db, self._verified(body))
        db.flush()
        db.refresh(order)
        assert order.status == "PAID"
        # mark_order_paid sets the Payment row to "succeeded", not "paid".
        assert payment.status == "succeeded"

    def test_amount_mismatch_does_not_mark_paid(self, db):
        order, payment = _make_order_and_payment(db, total_cents=12900)
        body = _paid_event_body(_TEST_SESSION_ID, 99.99)  # wrong amount
        provider = SpeedProvider()
        provider.handle_event(db, self._verified(body))
        db.flush()
        db.refresh(order)
        assert order.status == "PAYMENT_PENDING"

    def test_unknown_session_is_noop(self, db):
        body = _paid_event_body("cs_unknown_session", 129.00)
        provider = SpeedProvider()
        provider.handle_event(db, self._verified(body))
        # No exception, nothing written.

    def test_partial_payment_is_noop(self, db):
        order, _ = _make_order_and_payment(db)
        body = _paid_event_body(_TEST_SESSION_ID, order.total_cents / 100)
        body["event_type"] = "checkout_session.payment_paid"
        provider = SpeedProvider()
        provider.handle_event(db, self._verified(body))
        db.flush()
        db.refresh(order)
        assert order.status == "PAYMENT_PENDING"

    def test_created_event_is_noop(self, db):
        order, _ = _make_order_and_payment(db)
        body = _paid_event_body(_TEST_SESSION_ID, order.total_cents / 100)
        body["event_type"] = "checkout_session.created"
        provider = SpeedProvider()
        provider.handle_event(db, self._verified(body))
        db.flush()
        db.refresh(order)
        assert order.status == "PAYMENT_PENDING"


# ---------------------------------------------------------------------------
# create_payment_instructions (network mocked)
# ---------------------------------------------------------------------------


class TestCreatePaymentInstructions:
    def test_no_key_raises_not_configured(self, monkeypatch, db):
        monkeypatch.setattr(get_settings(), "speed_api_key", "")
        order, _ = _make_order_and_payment(db)
        provider = SpeedProvider()
        with pytest.raises(SpeedNotConfigured):
            provider.create_payment_instructions(order)

    def test_session_created_returns_instructions(self, monkeypatch, db):
        order, _ = _make_order_and_payment(db)
        captured: dict = {}

        class _FakeResponse:
            status_code = 201
            def json(self):
                return {
                    "id": _TEST_SESSION_ID,
                    "default_url": "https://checkout.tryspeed.com/pay/cs_test_xxx",
                    "url": "https://checkout.tryspeed.dev/pay/cs_test_xxx",
                }

        class _FakeClient:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def post(self, url, headers=None, json=None):
                captured["url"] = url
                captured["headers"] = headers
                captured["json"] = json
                return _FakeResponse()

        monkeypatch.setattr("app.payments.speed._client", lambda: _FakeClient())
        provider = SpeedProvider()
        instructions = provider.create_payment_instructions(order)

        assert instructions.provider == "crypto"
        assert instructions.details["provider_payment_id"] == _TEST_SESSION_ID
        assert instructions.details["checkout_url"].startswith("https://checkout.tryspeed.com")
        assert captured["url"].endswith("/checkout-sessions")
        assert captured["json"]["currency"] == "USD"
        assert captured["json"]["amount"] == pytest.approx(order.total_cents / 100, abs=0.01)

    def test_http_error_raises_speed_error(self, monkeypatch, db):
        order, _ = _make_order_and_payment(db)

        class _FakeResponse:
            status_code = 400
            text = '{"errors":[{"message":"invalid amount"}]}'
            def json(self):
                return {}

        class _FakeClient:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def post(self, url, headers=None, json=None):
                return _FakeResponse()

        monkeypatch.setattr("app.payments.speed._client", lambda: _FakeClient())
        provider = SpeedProvider()
        with pytest.raises(SpeedError, match="400"):
            provider.create_payment_instructions(order)
