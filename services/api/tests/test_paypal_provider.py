"""Tests for the PayPal provider (app/payments/paypal.py): order creation
payload, webhook verification, event handling and the return capture,
all against a scripted fake of PayPal's REST API."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.orders import Order
from app.models.payments import Payment
from app.payments import paypal
from app.payments.base import VerifiedEvent
from app.payments.paypal import (
    EVENT_CAPTURE_COMPLETED,
    EVENT_CAPTURE_DENIED,
    EVENT_CAPTURE_REFUNDED,
    EVENT_ORDER_APPROVED,
    PayPalError,
    PayPalNotConfigured,
    PayPalOrderNotApproved,
    PayPalProvider,
    build_verify_body,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_TEST_EMAIL = "paypal-provider-test@example.invalid"
_PP_ORDER_ID = "5O190127TN364715T"
_PP_ORDER_ID_2 = "5O190127TN364715U"
_CAPTURE_ID = "3C679366HH908993F"
_SITE = "https://www.example.test"
_WEBHOOK_ID = "8PT597110X687430LKGECATA"
# Captured before the autouse fixture swaps it for a stub, for the test
# that needs the real credential check.
_REAL_ACCESS_TOKEN = paypal._access_token
_SIG_HEADERS = {
    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
    "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-360caa42-fca2a594-1d93a270",
    "PAYPAL-TRANSMISSION-ID": "103e3700-8b0c-11e6-8695-6b62a8a99ac4",
    "PAYPAL-TRANSMISSION-SIG": "t9lhUf1e/…",
    "PAYPAL-TRANSMISSION-TIME": "2026-09-13T05:00:00Z",
    "Content-Type": "application/json",
}


def _cleanup(session):
    rows = session.execute(
        text("SELECT id FROM orders WHERE customer_email = :email"), {"email": _TEST_EMAIL}
    ).fetchall()
    if rows:
        ids = [r[0] for r in rows]
        session.execute(
            text("DELETE FROM payment_events WHERE payment_id IN (SELECT id FROM payments WHERE order_id = ANY(:ids))"),
            {"ids": ids},
        )
        session.execute(text("DELETE FROM payments WHERE order_id = ANY(:ids)"), {"ids": ids})
        session.execute(text("DELETE FROM order_events WHERE order_id = ANY(:ids)"), {"ids": ids})
        session.execute(text("DELETE FROM order_items WHERE order_id = ANY(:ids)"), {"ids": ids})
        session.execute(text("DELETE FROM orders WHERE id = ANY(:ids)"), {"ids": ids})
    session.execute(
        text("DELETE FROM payments WHERE provider_payment_id = ANY(:pids)"), {"pids": [_PP_ORDER_ID, _PP_ORDER_ID_2]}
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
    """Configured credentials + site URL so the provider doesn't raise
    PayPalNotConfigured unless a test clears them; a token that needs no
    HTTP; and a client that refuses the network unless a test installs
    a fake."""
    settings = get_settings()
    monkeypatch.setattr(settings, "paypal_client_id", "test-client-id")
    monkeypatch.setattr(settings, "paypal_client_secret", "test-client-secret")
    monkeypatch.setattr(settings, "paypal_environment", "sandbox")
    monkeypatch.setattr(settings, "paypal_webhook_id", _WEBHOOK_ID)
    monkeypatch.setattr(settings, "paypal_brand_name", "TCP")
    monkeypatch.setattr(settings, "public_site_url", _SITE)
    monkeypatch.setattr(settings, "fulfillment_mode", "manual")
    monkeypatch.setattr(paypal, "_access_token", lambda: "test-token")

    def _no_network():
        raise AssertionError("no HTTP call expected in this test")

    monkeypatch.setattr(paypal, "_client", _no_network)
    paypal._reset_token_cache()


class _Response:
    def __init__(self, status_code, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _FakePayPal:
    """Scripted PayPal: (METHOD, url suffix) → _Response or exception to
    raise. Records every call so tests can assert payloads."""

    def __init__(self, routes):
        self.routes = routes
        self.calls: list[tuple[str, str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return None

    def _dispatch(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        for (m, suffix), response in self.routes.items():
            if m == method and url.endswith(suffix):
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"unexpected {method} {url}")

    def get(self, url, **kwargs):
        return self._dispatch("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._dispatch("POST", url, **kwargs)


def _install(monkeypatch, routes) -> _FakePayPal:
    fake = _FakePayPal(routes)
    monkeypatch.setattr(paypal, "_client", lambda: fake)
    return fake


def _order_json(status="COMPLETED", capture_status="COMPLETED", value="129.00", currency="USD", order_id=_PP_ORDER_ID):
    return {
        "id": order_id,
        "status": status,
        "purchase_units": [
            {
                "reference_id": "default",
                "payments": {
                    "captures": [
                        {
                            "id": _CAPTURE_ID,
                            "status": capture_status,
                            "amount": {"currency_code": currency, "value": value},
                        }
                    ]
                },
            }
        ],
    }


def _created_json(rel="payer-action", order_id=_PP_ORDER_ID):
    return {
        "id": order_id,
        "status": "PAYER_ACTION_REQUIRED" if rel == "payer-action" else "CREATED",
        "links": [
            {"href": f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{order_id}", "rel": "self", "method": "GET"},
            {"href": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}", "rel": rel, "method": "GET"},
        ],
    }


def _make_order_and_payment(
    db,
    *,
    total_cents: int = 12900,
    paypal_order_id: str | None = _PP_ORDER_ID,
    payment_status: str = "pending",
    order_status: str = "PAYMENT_PENDING",
) -> tuple[Order, Payment]:
    order = Order(
        customer_email=_TEST_EMAIL,
        customer_name="Pay Pal",
        public_order_number=f"PEN-{uuid.uuid4().hex[:6].upper()}",
        access_token=uuid.uuid4().hex,
        status=order_status,
        subtotal_cents=total_cents,
        shipping_cents=0,
        tax_cents=0,
        total_cents=total_cents,
    )
    db.add(order)
    db.flush()
    payment = Payment(
        order_id=order.id,
        provider="paypal",
        provider_payment_id=paypal_order_id,
        status=payment_status,
        amount_cents=total_cents,
        currency="usd",
        provider_data={"provider_payment_id": paypal_order_id, "approve_url": "https://www.sandbox.paypal.com/checkoutnow?token=x"},
    )
    db.add(payment)
    db.flush()
    return order, payment


def _capture_event(order: Order, *, event_id="WH-TEST-1", value="129.00", currency="USD", custom_id=None, paypal_order_id=_PP_ORDER_ID):
    return {
        "id": event_id,
        "event_type": EVENT_CAPTURE_COMPLETED,
        "resource_type": "capture",
        "resource": {
            "id": _CAPTURE_ID,
            "status": "COMPLETED",
            "amount": {"currency_code": currency, "value": value},
            "custom_id": custom_id if custom_id is not None else order.public_order_number,
            "supplementary_data": {"related_ids": {"order_id": paypal_order_id}},
        },
    }


def _verified(event: dict) -> VerifiedEvent:
    resource = event["resource"]
    custom = resource.get("custom_id") or ((resource.get("purchase_units") or [{}])[0].get("custom_id"))
    return VerifiedEvent(external_id=event["id"], event_type=event["event_type"], order_id=custom or None, raw=event)


def _order_events(db, order_id) -> list[str]:
    return [
        r[0]
        for r in db.execute(
            text("SELECT event_type FROM order_events WHERE order_id = :oid ORDER BY created_at, event_type"), {"oid": order_id}
        )
    ]


def _payment_events(db, payment_id) -> list[str]:
    return [
        r[0]
        for r in db.execute(
            text("SELECT event_type FROM payment_events WHERE payment_id = :pid ORDER BY created_at, event_type"), {"pid": payment_id}
        )
    ]


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------


def test_create_instructions_requires_credentials(db, monkeypatch):
    monkeypatch.setattr(paypal, "_access_token", _REAL_ACCESS_TOKEN)
    monkeypatch.setattr(get_settings(), "paypal_client_id", "")
    order, _ = _make_order_and_payment(db)
    with pytest.raises(PayPalNotConfigured):
        PayPalProvider().create_payment_instructions(order)


def test_create_instructions_requires_a_site_url(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "public_site_url", "")
    order, _ = _make_order_and_payment(db)
    with pytest.raises(PayPalNotConfigured):
        PayPalProvider().create_payment_instructions(order)


def test_create_instructions_posts_a_peptide_free_order_and_returns_the_approve_link(db, monkeypatch):
    fake = _install(monkeypatch, {("POST", "/v2/checkout/orders"): _Response(201, _created_json())})
    order, _ = _make_order_and_payment(db, total_cents=12950)

    before = datetime.now(timezone.utc)
    instructions = PayPalProvider().create_payment_instructions(order)

    assert instructions.provider == "paypal"
    assert instructions.details["provider_payment_id"] == _PP_ORDER_ID
    assert instructions.details["approve_url"] == f"https://www.sandbox.paypal.com/checkoutnow?token={_PP_ORDER_ID}"
    assert instructions.details["checkout_url"] == instructions.details["approve_url"]
    assert instructions.details["usd_total_cents"] == 12950
    assert instructions.details["paypal_status"] == "PAYER_ACTION_REQUIRED"
    expires = datetime.fromisoformat(instructions.details["expires_at"])
    assert timedelta(hours=2, minutes=59) < expires - before < timedelta(hours=3, minutes=1)

    (method, url, kwargs), = fake.calls
    assert method == "POST" and url == "https://api-m.sandbox.paypal.com/v2/checkout/orders"
    assert kwargs["headers"]["Authorization"] == "Bearer test-token"
    body = kwargs["json"]
    assert body["intent"] == "CAPTURE"
    unit = body["purchase_units"][0]
    assert unit["amount"] == {"currency_code": "USD", "value": "129.50"}
    assert unit["custom_id"] == order.public_order_number
    assert unit["description"] == f"TCP Order {order.public_order_number}"
    context = body["payment_source"]["paypal"]["experience_context"]
    assert context["brand_name"] == "TCP"
    assert context["user_action"] == "PAY_NOW"
    assert context["shipping_preference"] == "NO_SHIPPING"
    assert context["return_url"] == f"{_SITE}/order/{order.access_token}"
    assert context["cancel_url"] == context["return_url"]
    # Compliance: nothing PayPal sees names a product.
    serialised = json.dumps(body).lower()
    for word in ("peptide", "pen", "mg", "glp", "bpc"):
        assert word not in serialised.replace(order.public_order_number.lower(), "")


def test_create_instructions_accepts_the_legacy_approve_rel(db, monkeypatch):
    _install(monkeypatch, {("POST", "/v2/checkout/orders"): _Response(201, _created_json(rel="approve"))})
    order, _ = _make_order_and_payment(db)
    instructions = PayPalProvider().create_payment_instructions(order)
    assert instructions.details["approve_url"].endswith(f"token={_PP_ORDER_ID}")


def test_create_instructions_raises_on_paypal_error(db, monkeypatch):
    _install(monkeypatch, {("POST", "/v2/checkout/orders"): _Response(401, {"error": "invalid_client"})})
    order, _ = _make_order_and_payment(db)
    with pytest.raises(PayPalError):
        PayPalProvider().create_payment_instructions(order)


def test_create_instructions_raises_without_an_approve_link(db, monkeypatch):
    _install(monkeypatch, {("POST", "/v2/checkout/orders"): _Response(201, {"id": _PP_ORDER_ID, "links": []})})
    order, _ = _make_order_and_payment(db)
    with pytest.raises(PayPalError):
        PayPalProvider().create_payment_instructions(order)


# ---------------------------------------------------------------------------
# Webhook verification
# ---------------------------------------------------------------------------


def _raw(event: dict) -> bytes:
    return json.dumps(event, separators=(",", ":")).encode()


def test_verify_webhook_rejects_when_webhook_id_is_blank(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "paypal_webhook_id", "")
    order, _ = _make_order_and_payment(db)
    with pytest.raises(PayPalNotConfigured):
        PayPalProvider().verify_webhook(_SIG_HEADERS, _raw(_capture_event(order)))


def test_verify_webhook_rejects_missing_signature_headers(db):
    order, _ = _make_order_and_payment(db)
    headers = {k: v for k, v in _SIG_HEADERS.items() if k != "PAYPAL-TRANSMISSION-SIG"}
    with pytest.raises(PayPalError, match="paypal-transmission-sig"):
        PayPalProvider().verify_webhook(headers, _raw(_capture_event(order)))


def test_verify_webhook_rejects_non_event_bodies(db):
    with pytest.raises(PayPalError):
        PayPalProvider().verify_webhook(_SIG_HEADERS, b"")
    with pytest.raises(PayPalError):
        PayPalProvider().verify_webhook(_SIG_HEADERS, b"not json")
    with pytest.raises(PayPalError):
        PayPalProvider().verify_webhook(_SIG_HEADERS, b'{"id": "WH-1", "event_type": "X"}')


def test_verify_webhook_rejects_when_paypal_reports_failure(db, monkeypatch):
    _install(
        monkeypatch,
        {("POST", "/v1/notifications/verify-webhook-signature"): _Response(200, {"verification_status": "FAILURE"})},
    )
    order, _ = _make_order_and_payment(db)
    with pytest.raises(PayPalError, match="FAILURE"):
        PayPalProvider().verify_webhook(_SIG_HEADERS, _raw(_capture_event(order)))


def test_verify_webhook_rejects_when_verification_call_fails(db, monkeypatch):
    _install(monkeypatch, {("POST", "/v1/notifications/verify-webhook-signature"): httpx.ConnectError("boom")})
    order, _ = _make_order_and_payment(db)
    with pytest.raises(PayPalError):
        PayPalProvider().verify_webhook(_SIG_HEADERS, _raw(_capture_event(order)))


def test_verify_webhook_success_splices_the_raw_body_and_returns_the_event(db, monkeypatch):
    fake = _install(
        monkeypatch,
        {("POST", "/v1/notifications/verify-webhook-signature"): _Response(200, {"verification_status": "SUCCESS"})},
    )
    order, _ = _make_order_and_payment(db)
    event = _capture_event(order, event_id="WH-TEST-verify")
    # Odd spacing PayPal would never normalise for us — must reach the
    # verify call byte-for-byte.
    raw = json.dumps(event, indent=3).encode()

    verified = PayPalProvider().verify_webhook(_SIG_HEADERS, raw)

    assert verified.external_id == "WH-TEST-verify"
    assert verified.event_type == EVENT_CAPTURE_COMPLETED
    assert verified.order_id == order.public_order_number
    assert verified.raw == event
    (_, url, kwargs), = fake.calls
    assert url.endswith("/v1/notifications/verify-webhook-signature")
    sent = kwargs["content"]
    assert sent.endswith(b',"webhook_event":' + raw + b"}")
    parsed = json.loads(sent)
    assert parsed["webhook_id"] == _WEBHOOK_ID
    assert parsed["transmission_id"] == _SIG_HEADERS["PAYPAL-TRANSMISSION-ID"]
    assert parsed["auth_algo"] == "SHA256withRSA"
    assert parsed["cert_url"] == _SIG_HEADERS["PAYPAL-CERT-URL"]
    assert parsed["transmission_sig"] == _SIG_HEADERS["PAYPAL-TRANSMISSION-SIG"]
    assert parsed["transmission_time"] == _SIG_HEADERS["PAYPAL-TRANSMISSION-TIME"]
    assert parsed["webhook_event"] == event


def test_build_verify_body_keeps_raw_bytes():
    raw = b'{"id": "WH-1",  "event_type": "X", "resource": {}}'
    body = build_verify_body({"auth_algo": "A", "cert_url": "C", "transmission_id": "T", "transmission_sig": "S", "transmission_time": "M"}, "W", raw)
    assert body == b'{"auth_algo":"A","cert_url":"C","transmission_id":"T","transmission_sig":"S","transmission_time":"M","webhook_id":"W","webhook_event":' + raw + b"}"
    assert json.loads(body)["webhook_event"]["id"] == "WH-1"


# ---------------------------------------------------------------------------
# PAYMENT.CAPTURE.COMPLETED
# ---------------------------------------------------------------------------


def test_capture_completed_marks_order_paid_after_refetch(db, monkeypatch):
    fake = _install(monkeypatch, {("GET", f"/v2/checkout/orders/{_PP_ORDER_ID}"): _Response(200, _order_json())})
    order, payment = _make_order_and_payment(db)

    result = PayPalProvider().handle_event(db, _verified(_capture_event(order)))

    assert result == order.id
    db.refresh(order)
    db.refresh(payment)
    assert order.status == "PAID"
    assert payment.status == "succeeded"
    assert payment.provider_payment_id == _PP_ORDER_ID
    assert payment.provider_data["capture_id"] == _CAPTURE_ID
    assert payment.provider_data["captured_amount"] == "129.00"
    assert [m for m, _, _ in fake.calls] == ["GET"]
    assert "payment.confirmed" in _payment_events(db, payment.id)
    assert "paypal.capture_completed" in _payment_events(db, payment.id)
    assert "status_changed" in _order_events(db, order.id)
    assert "payment_amount_mismatch" not in _order_events(db, order.id)


def test_capture_completed_blocks_on_amount_mismatch(db, monkeypatch):
    _install(monkeypatch, {("GET", f"/v2/checkout/orders/{_PP_ORDER_ID}"): _Response(200, _order_json(value="100.00"))})
    order, payment = _make_order_and_payment(db, total_cents=12900)

    result = PayPalProvider().handle_event(db, _verified(_capture_event(order, value="100.00")))

    assert result is None
    db.refresh(order)
    db.refresh(payment)
    assert order.status == "PAYMENT_PENDING"
    assert payment.status == "pending"
    assert "payment_amount_mismatch" in _order_events(db, order.id)


def test_capture_completed_blocks_on_currency_mismatch(db, monkeypatch):
    _install(monkeypatch, {("GET", f"/v2/checkout/orders/{_PP_ORDER_ID}"): _Response(200, _order_json(currency="EUR"))})
    order, _ = _make_order_and_payment(db)
    assert PayPalProvider().handle_event(db, _verified(_capture_event(order, currency="EUR"))) is None
    db.refresh(order)
    assert order.status == "PAYMENT_PENDING"
    assert "payment_amount_mismatch" in _order_events(db, order.id)


def test_capture_completed_raises_when_paypal_does_not_agree(db, monkeypatch):
    _install(monkeypatch, {("GET", f"/v2/checkout/orders/{_PP_ORDER_ID}"): _Response(200, _order_json(status="APPROVED", capture_status="PENDING"))})
    order, _ = _make_order_and_payment(db)
    with pytest.raises(PayPalError, match="not COMPLETED"):
        PayPalProvider().handle_event(db, _verified(_capture_event(order)))
    db.refresh(order)
    assert order.status == "PAYMENT_PENDING"


def test_capture_completed_raises_when_refetch_fails(db, monkeypatch):
    _install(monkeypatch, {("GET", f"/v2/checkout/orders/{_PP_ORDER_ID}"): httpx.ConnectError("boom")})
    order, _ = _make_order_and_payment(db)
    with pytest.raises(PayPalError):
        PayPalProvider().handle_event(db, _verified(_capture_event(order)))


def test_capture_completed_refuses_custom_id_mismatch_without_http(db):
    order, payment = _make_order_and_payment(db)
    result = PayPalProvider().handle_event(db, _verified(_capture_event(order, custom_id="PEN-SOMEONE")))
    assert result is None
    db.refresh(order)
    assert order.status == "PAYMENT_PENDING"
    assert _payment_events(db, payment.id) == []


def test_capture_completed_for_unknown_order_is_ignored(db):
    order, _ = _make_order_and_payment(db)
    result = PayPalProvider().handle_event(db, _verified(_capture_event(order, paypal_order_id="UNKNOWN0000000001")))
    assert result is None
    db.refresh(order)
    assert order.status == "PAYMENT_PENDING"


def test_capture_completed_after_order_already_paid_is_recorded_only(db):
    order, payment = _make_order_and_payment(db, payment_status="succeeded", order_status="PAID")
    result = PayPalProvider().handle_event(db, _verified(_capture_event(order)))
    assert result is None
    db.refresh(order)
    assert order.status == "PAID"
    assert _payment_events(db, payment.id) == [EVENT_CAPTURE_COMPLETED.lower()]


# ---------------------------------------------------------------------------
# Other events
# ---------------------------------------------------------------------------


def test_capture_denied_marks_payment_failed_and_order_stays_pending(db):
    order, payment = _make_order_and_payment(db)
    event = _capture_event(order, event_id="WH-TEST-denied")
    event["event_type"] = EVENT_CAPTURE_DENIED
    event["resource"]["status"] = "DECLINED"

    assert PayPalProvider().handle_event(db, _verified(event)) is None

    db.refresh(order)
    db.refresh(payment)
    assert order.status == "PAYMENT_PENDING"
    assert payment.status == "failed"
    assert "payment_denied" in _order_events(db, order.id)
    assert _payment_events(db, payment.id) == [EVENT_CAPTURE_DENIED.lower()]


def test_refund_is_recorded_without_touching_the_order(db):
    order, payment = _make_order_and_payment(db, payment_status="succeeded", order_status="PAID")
    event = _capture_event(order, event_id="WH-TEST-refund")
    event["event_type"] = EVENT_CAPTURE_REFUNDED
    event["resource"] = {"id": "REFUND1", "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "129.00"}, "custom_id": order.public_order_number, "supplementary_data": {"related_ids": {"order_id": _PP_ORDER_ID}}}

    assert PayPalProvider().handle_event(db, _verified(event)) is None

    db.refresh(order)
    db.refresh(payment)
    assert order.status == "PAID"
    assert payment.status == "succeeded"
    assert "payment_refunded" in _order_events(db, order.id)


def _approved_event(order: Order, event_id="WH-TEST-approved"):
    return {
        "id": event_id,
        "event_type": EVENT_ORDER_APPROVED,
        "resource_type": "checkout-order",
        "resource": {
            "id": _PP_ORDER_ID,
            "status": "APPROVED",
            "purchase_units": [{"reference_id": "default", "custom_id": order.public_order_number}],
        },
    }


def test_order_approved_captures_server_side(db, monkeypatch):
    fake = _install(monkeypatch, {("POST", f"/v2/checkout/orders/{_PP_ORDER_ID}/capture"): _Response(201, _order_json())})
    order, payment = _make_order_and_payment(db)

    result = PayPalProvider().handle_event(db, _verified(_approved_event(order)))

    assert result == order.id
    db.refresh(order)
    db.refresh(payment)
    assert order.status == "PAID"
    assert payment.status == "succeeded"
    (_, url, kwargs), = fake.calls
    assert url.endswith(f"/v2/checkout/orders/{_PP_ORDER_ID}/capture")
    assert kwargs["headers"]["PayPal-Request-Id"] == f"{_PP_ORDER_ID}:capture"
    assert EVENT_ORDER_APPROVED.lower() in _payment_events(db, payment.id)


def test_order_approved_when_not_actually_approved_is_a_noop(db, monkeypatch):
    _install(
        monkeypatch,
        {("POST", f"/v2/checkout/orders/{_PP_ORDER_ID}/capture"): _Response(422, {"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": "ORDER_NOT_APPROVED"}]})},
    )
    order, _ = _make_order_and_payment(db)
    assert PayPalProvider().handle_event(db, _verified(_approved_event(order))) is None
    db.refresh(order)
    assert order.status == "PAYMENT_PENDING"


def test_order_approved_capture_failure_is_best_effort(db, monkeypatch):
    _install(monkeypatch, {("POST", f"/v2/checkout/orders/{_PP_ORDER_ID}/capture"): httpx.ConnectError("boom")})
    order, _ = _make_order_and_payment(db)
    assert PayPalProvider().handle_event(db, _verified(_approved_event(order))) is None
    db.refresh(order)
    assert order.status == "PAYMENT_PENDING"


def test_order_approved_after_paid_does_not_capture_again(db):
    order, payment = _make_order_and_payment(db, payment_status="succeeded", order_status="PAID")
    assert PayPalProvider().handle_event(db, _verified(_approved_event(order))) is None  # no HTTP: _client would assert
    assert _payment_events(db, payment.id) == [EVENT_ORDER_APPROVED.lower()]


# ---------------------------------------------------------------------------
# The customer's return (capture_for_return)
# ---------------------------------------------------------------------------


def test_capture_for_return_marks_order_paid(db, monkeypatch):
    _install(monkeypatch, {("POST", f"/v2/checkout/orders/{_PP_ORDER_ID}/capture"): _Response(201, _order_json())})
    order, payment = _make_order_and_payment(db)

    result = PayPalProvider().capture_for_return(db, order)

    assert result == order.id
    db.refresh(order)
    db.refresh(payment)
    assert order.status == "PAID"
    assert payment.status == "succeeded"
    assert payment.provider_data["capture_id"] == _CAPTURE_ID
    assert "paypal.capture_completed" in _payment_events(db, payment.id)


def test_capture_for_return_already_captured_refetches_and_settles(db, monkeypatch):
    fake = _install(
        monkeypatch,
        {
            ("POST", f"/v2/checkout/orders/{_PP_ORDER_ID}/capture"): _Response(422, {"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": "ORDER_ALREADY_CAPTURED"}]}),
            ("GET", f"/v2/checkout/orders/{_PP_ORDER_ID}"): _Response(200, _order_json()),
        },
    )
    order, _ = _make_order_and_payment(db)
    assert PayPalProvider().capture_for_return(db, order) == order.id
    assert [m for m, _, _ in fake.calls] == ["POST", "GET"]
    db.refresh(order)
    assert order.status == "PAID"


def test_capture_for_return_not_approved_raises(db, monkeypatch):
    _install(
        monkeypatch,
        {("POST", f"/v2/checkout/orders/{_PP_ORDER_ID}/capture"): _Response(422, {"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": "ORDER_NOT_APPROVED"}]})},
    )
    order, _ = _make_order_and_payment(db)
    with pytest.raises(PayPalOrderNotApproved):
        PayPalProvider().capture_for_return(db, order)
    db.refresh(order)
    assert order.status == "PAYMENT_PENDING"


def test_capture_for_return_pending_capture_sets_processing(db, monkeypatch):
    _install(
        monkeypatch,
        {("POST", f"/v2/checkout/orders/{_PP_ORDER_ID}/capture"): _Response(201, _order_json(status="COMPLETED", capture_status="PENDING"))},
    )
    order, payment = _make_order_and_payment(db)
    assert PayPalProvider().capture_for_return(db, order) is None
    db.refresh(order)
    db.refresh(payment)
    assert order.status == "PAYMENT_PENDING"
    assert payment.status == "processing"
    assert "paypal.capture_pending" in _payment_events(db, payment.id)


def test_capture_for_return_amount_mismatch_blocks(db, monkeypatch):
    _install(monkeypatch, {("POST", f"/v2/checkout/orders/{_PP_ORDER_ID}/capture"): _Response(201, _order_json(value="1.00"))})
    order, _ = _make_order_and_payment(db)
    assert PayPalProvider().capture_for_return(db, order) is None
    db.refresh(order)
    assert order.status == "PAYMENT_PENDING"
    assert "payment_amount_mismatch" in _order_events(db, order.id)


def test_capture_for_return_is_a_noop_once_paid(db):
    order, _ = _make_order_and_payment(db, payment_status="succeeded", order_status="PAID")
    assert PayPalProvider().capture_for_return(db, order) is None  # no HTTP


def test_capture_for_return_refuses_without_a_paypal_order(db):
    order, _ = _make_order_and_payment(db, paypal_order_id=None)
    with pytest.raises(PayPalError):
        PayPalProvider().capture_for_return(db, order)


def test_capture_for_return_refuses_a_superseded_row(db):
    order, _ = _make_order_and_payment(db, payment_status="superseded")
    with pytest.raises(PayPalError):
        PayPalProvider().capture_for_return(db, order)
