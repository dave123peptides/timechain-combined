"""Tests for the Whop card / Apple Pay provider (app/payments/whop.py)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.orders import Order
from app.models.payments import Payment
from app.payments import whop
from app.payments.base import VerifiedEvent
from app.payments.whop import WhopError, WhopNotConfigured, WhopProvider, compute_signature, parse_money
from app.services import payments as payment_services

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_TEST_EMAIL = "whop-provider-test@example.invalid"
_KEY = "test-whop-api-key"
_SECRET = "ws_0123456789abcdef0123456789abcdef"
_CONFIG_ID = "ch_test_whop_000000000001"
_CONFIG_ID_2 = "ch_test_whop_000000000002"
_PAY_ID = "pay_test_whop_000000000001"
_MSG_ID = "msg_test_whop_000000000001"
_SITE = "https://www.example.test"
_BASE = "https://sandbox-api.whop.com/api/v1"
_PIN = "2026-09-11-1"
# verify_webhook never touches the database; a stand-in order is enough.
_ORDER = SimpleNamespace(public_order_number="PEN-VERIFY", access_token="verify-token")


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
        session.execute(text("DELETE FROM payments WHERE order_id = ANY(:ids)"), {"ids": order_ids})
        session.execute(text("DELETE FROM order_events WHERE order_id = ANY(:ids)"), {"ids": order_ids})
        session.execute(text("DELETE FROM order_items WHERE order_id = ANY(:ids)"), {"ids": order_ids})
        session.execute(text("DELETE FROM orders WHERE id = ANY(:ids)"), {"ids": order_ids})
    session.execute(
        text("DELETE FROM payments WHERE provider_payment_id = ANY(:pids)"),
        {"pids": [_CONFIG_ID, _CONFIG_ID_2, _PAY_ID]},
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
    """Every test gets a configured key, secret and site URL so the
    provider doesn't raise WhopNotConfigured unless the test clears them,
    plus a client that refuses to touch the network unless the test
    installs a fake."""
    settings = get_settings()
    monkeypatch.setattr(settings, "whop_api_key", _KEY)
    monkeypatch.setattr(settings, "whop_webhook_secret", _SECRET)
    monkeypatch.setattr(settings, "whop_environment", "sandbox")
    monkeypatch.setattr(settings, "whop_api_version_date", _PIN)
    monkeypatch.setattr(settings, "whop_account_id", "")
    monkeypatch.setattr(settings, "public_site_url", _SITE)
    monkeypatch.setattr(settings, "fulfillment_mode", "manual")

    def _no_network():
        raise AssertionError("no HTTP call expected in this test")

    monkeypatch.setattr(whop, "_client", _no_network)


def _make_order_and_payment(
    db,
    *,
    total_cents: int = 12900,
    provider_payment_id: str | None = _CONFIG_ID,
    payment_status: str = "pending",
) -> tuple[Order, Payment]:
    order = Order(
        customer_email=_TEST_EMAIL,
        customer_name="Card Buyer",
        public_order_number=f"PEN-{uuid.uuid4().hex[:6].upper()}",
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
        provider="whop",
        provider_payment_id=provider_payment_id,
        status=payment_status,
        amount_cents=total_cents,
        currency="usd",
        provider_data={"checkout_url": f"https://whop.com/checkout/plan_test/?session={provider_payment_id or ''}"},
    )
    db.add(payment)
    db.flush()
    return order, payment


def _money(amount: float, shape: str, currency: str = "usd"):
    if shape == "number":
        return float(amount)
    if shape == "string":
        return f"{amount:.2f}"
    if shape == "object":
        return {"amount": f"{amount:.2f}", "currency": currency, "decimals": 2, "display_decimals": 2}
    raise ValueError(shape)


def _payment_obj(
    order,
    *,
    pay_id: str = _PAY_ID,
    status: str = "paid",
    substatus: str | None = "succeeded",
    total: float | None = 129.0,
    shape: str = "number",
    currency: str = "usd",
    config_id: str = _CONFIG_ID,
    order_number: str | None = None,
    **extra,
) -> dict:
    """A Whop payment object as delivered in `data` (and by GET /payments)."""
    data = {
        "id": pay_id,
        "status": status,
        "substatus": substatus,
        "currency": currency,
        "total": _money(total, shape, currency) if total is not None else None,
        "subtotal": _money(total, shape, currency) if total is not None else None,
        "amount_after_fees": _money(total * 0.95, shape, currency) if total is not None else None,
        "checkout_configuration_id": config_id,
        "metadata": {"order_number": order_number or order.public_order_number},
        "card_brand": "visa",
        "card_last4": "4242",
        "payment_method_type": "card",
        "paid_at": "2026-09-14T12:00:00Z",
    }
    data.update(extra)
    return data


def _envelope(order, *, event_type: str = "payment.succeeded", data: dict | None = None, msg_id: str = _MSG_ID, **kw) -> dict:
    return {
        "id": msg_id,
        "type": event_type,
        "api_version": "v1",
        "timestamp": "2026-09-14T12:00:00Z",
        "data": data if data is not None else _payment_obj(order, **kw),
    }


def _body(envelope: dict) -> bytes:
    return json.dumps(envelope).encode()


def _headers(body: bytes, *, secret: str = _SECRET, msg_id: str = _MSG_ID, ts=None, signature: str | None = None) -> dict:
    ts = int(time.time()) if ts is None else ts
    sig = compute_signature(secret, msg_id, ts, body) if signature is None else signature
    return {
        "Content-Type": "application/json",
        "webhook-id": msg_id,
        "webhook-timestamp": str(ts),
        "webhook-signature": sig,
    }


def _verified(envelope: dict) -> VerifiedEvent:
    data = envelope.get("data") or {}
    return VerifiedEvent(
        external_id=envelope["id"],
        event_type=envelope["type"],
        order_id=(data.get("metadata") or {}).get("order_number"),
        raw=envelope,
    )


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _FakeClient:
    """Records every call; answers GET/POST from the responses given."""

    def __init__(self, *, get=None, post=None, get_raises=None):
        self.calls: list[tuple[str, str, dict]] = []
        self._get = get
        self._post = post
        self._get_raises = get_raises

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get(self, url, headers=None):
        self.calls.append(("get", url, {"headers": headers}))
        if self._get_raises is not None:
            raise self._get_raises
        return self._get if not callable(self._get) else self._get(url)

    def post(self, url, headers=None, json=None):
        self.calls.append(("post", url, {"headers": headers, "json": json}))
        return self._post


def _install(monkeypatch, client: _FakeClient) -> _FakeClient:
    monkeypatch.setattr(whop, "_client", lambda: client)
    return client


def _fresh(order, **kw) -> _FakeResponse:
    """What GET /payments/{id} answers."""
    return _FakeResponse(200, _payment_obj(order, **kw))


def _created(
    config_id: str = _CONFIG_ID,
    *,
    status: int = 201,
    purchase_url: str | None = None,
    wrapped: bool = False,
    plan_id: str | None = "plan_test_000001",
) -> _FakeResponse:
    data = {
        "id": config_id,
        "mode": "payment",
        "purchase_url": purchase_url if purchase_url is not None else f"https://whop.com/checkout/{plan_id}/?session={config_id}",
    }
    if plan_id:
        data["plan"] = {"id": plan_id}
    return _FakeResponse(status, {"data": data} if wrapped else data)


def _payment_event_types(db, payment_id) -> list[str]:
    return [
        r[0]
        for r in db.execute(
            text("SELECT event_type FROM payment_events WHERE payment_id = :pid ORDER BY created_at, event_type"),
            {"pid": payment_id},
        )
    ]


def _order_event_types(db, order_id) -> list[str]:
    return [
        r[0]
        for r in db.execute(
            text("SELECT event_type FROM order_events WHERE order_id = :oid ORDER BY created_at"),
            {"oid": order_id},
        )
    ]


def _mismatch_events(db, order_id) -> list[dict]:
    return [
        r[0]
        for r in db.execute(
            text("SELECT data FROM order_events WHERE order_id = :oid AND event_type = 'payment_amount_mismatch'"),
            {"oid": order_id},
        )
    ]


# ---------------------------------------------------------------------------
# compute_signature / parse_money
# ---------------------------------------------------------------------------


class TestComputeSignature:
    def test_matches_independent_hmac_base64(self):
        body = b'{"id":"msg_x","type":"payment.succeeded","data":{}}'
        digest = hmac.new(_SECRET.encode(), b"msg_x.1700000000." + body, hashlib.sha256).digest()
        assert compute_signature(_SECRET, "msg_x", 1700000000, body) == "v1," + base64.b64encode(digest).decode()

    def test_secret_is_used_verbatim_not_base64_decoded(self):
        # Standard Webhooks libraries strip a prefix and base64-decode the
        # rest; Whop signs with the literal secret bytes (prefix included).
        body = b"{}"
        decoded_key = base64.b64decode(_SECRET.split("_", 1)[1] + "==")
        wrong = "v1," + base64.b64encode(
            hmac.new(decoded_key, b"msg_x.1700000000." + body, hashlib.sha256).digest()
        ).decode()
        assert compute_signature(_SECRET, "msg_x", 1700000000, body) != wrong

    def test_timestamp_int_and_str_sign_identically(self):
        assert compute_signature(_SECRET, "m", 1700000000, b"x") == compute_signature(_SECRET, "m", "1700000000", b"x")

    def test_different_secret_differs(self):
        assert compute_signature("ws_other", "m", 1, b"x") != compute_signature(_SECRET, "m", 1, b"x")

    def test_body_bytes_are_signed_raw(self):
        assert compute_signature(_SECRET, "m", 1, b'{"a":1}') != compute_signature(_SECRET, "m", 1, b'{"a": 1}')


class TestParseMoney:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (129, 129.0),
            (129.5, 129.5),
            ("129.50", 129.5),
            (" 12 ", 12.0),
            ({"amount": "10.00", "currency": "usd", "decimals": 2}, 10.0),
            ({"amount": 7, "currency": "usd"}, 7.0),
            (None, None),
            ("", None),
            ("abc", None),
            ("NaN", None),
            (True, None),
            ({"currency": "usd"}, None),
            ([1], None),
        ],
    )
    def test_shapes(self, value, expected):
        assert parse_money(value) == expected


# ---------------------------------------------------------------------------
# verify_webhook
# ---------------------------------------------------------------------------


class TestVerifyWebhook:
    def test_valid_signature_returns_event(self):
        envelope = _envelope(_ORDER)
        body = _body(envelope)
        event = WhopProvider().verify_webhook(_headers(body), body)
        assert event.event_type == "payment.succeeded"
        assert event.external_id == _MSG_ID
        assert event.order_id == "PEN-VERIFY"
        assert event.raw == envelope

    def test_external_id_falls_back_to_webhook_id_header(self):
        envelope = _envelope(_ORDER)
        del envelope["id"]
        body = _body(envelope)
        assert WhopProvider().verify_webhook(_headers(body, msg_id="msg_hdr_only"), body).external_id == "msg_hdr_only"

    def test_order_id_falls_back_to_checkout_configuration_metadata(self):
        data = _payment_obj(_ORDER)
        del data["metadata"]
        data["checkout_configuration"] = {"id": _CONFIG_ID, "metadata": {"order_number": "PEN-NESTED"}}
        body = _body(_envelope(_ORDER, data=data))
        assert WhopProvider().verify_webhook(_headers(body), body).order_id == "PEN-NESTED"

    def test_order_id_none_without_metadata(self):
        data = _payment_obj(_ORDER)
        del data["metadata"]
        body = _body(_envelope(_ORDER, data=data))
        assert WhopProvider().verify_webhook(_headers(body), body).order_id is None

    def test_multiple_space_separated_signatures_any_match_accepted(self):
        body = _body(_envelope(_ORDER))
        ts = int(time.time())
        valid = compute_signature(_SECRET, _MSG_ID, ts, body)
        headers = _headers(body, ts=ts, signature=f"v1,AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= {valid}")
        assert WhopProvider().verify_webhook(headers, body).event_type == "payment.succeeded"

    def test_wrong_secret_raises(self):
        body = _body(_envelope(_ORDER))
        with pytest.raises(WhopError, match="does not match"):
            WhopProvider().verify_webhook(_headers(body, secret="ws_someone_else"), body)

    def test_tampered_body_raises(self):
        body = _body(_envelope(_ORDER))
        headers = _headers(body)
        with pytest.raises(WhopError, match="does not match"):
            WhopProvider().verify_webhook(headers, body.replace(b"129.0", b"1.0"))

    def test_non_v1_signature_ignored(self):
        body = _body(_envelope(_ORDER))
        ts = int(time.time())
        valid = compute_signature(_SECRET, _MSG_ID, ts, body)
        with pytest.raises(WhopError, match="does not match"):
            WhopProvider().verify_webhook(_headers(body, ts=ts, signature="v2," + valid[3:]), body)

    def test_timestamp_too_old_raises(self):
        body = _body(_envelope(_ORDER))
        with pytest.raises(WhopError, match="tolerance"):
            WhopProvider().verify_webhook(_headers(body, ts=int(time.time()) - 600), body)

    def test_timestamp_in_future_raises(self):
        body = _body(_envelope(_ORDER))
        with pytest.raises(WhopError, match="tolerance"):
            WhopProvider().verify_webhook(_headers(body, ts=int(time.time()) + 600), body)

    def test_non_integer_timestamp_raises(self):
        body = _body(_envelope(_ORDER))
        headers = {**_headers(body), "webhook-timestamp": "soon"}
        with pytest.raises(WhopError, match="not an integer"):
            WhopProvider().verify_webhook(headers, body)

    @pytest.mark.parametrize("missing", ["webhook-id", "webhook-timestamp", "webhook-signature"])
    def test_missing_header_raises(self, missing):
        body = _body(_envelope(_ORDER))
        headers = _headers(body)
        del headers[missing]
        with pytest.raises(WhopError, match="Missing"):
            WhopProvider().verify_webhook(headers, body)

    def test_header_names_case_insensitive(self):
        body = _body(_envelope(_ORDER))
        headers = {k.upper(): v for k, v in _headers(body).items()}
        assert WhopProvider().verify_webhook(headers, body).external_id == _MSG_ID

    def test_non_json_body_raises(self):
        body = b"not json at all"
        with pytest.raises(WhopError, match="Unparseable"):
            WhopProvider().verify_webhook(_headers(body), body)

    def test_body_not_object_raises(self):
        body = b"[1, 2]"
        with pytest.raises(WhopError, match="not an object"):
            WhopProvider().verify_webhook(_headers(body), body)

    def test_body_without_type_raises(self):
        envelope = _envelope(_ORDER)
        del envelope["type"]
        body = _body(envelope)
        with pytest.raises(WhopError, match="event type"):
            WhopProvider().verify_webhook(_headers(body), body)

    def test_body_without_data_raises(self):
        envelope = _envelope(_ORDER)
        envelope["data"] = "pay_x"
        body = _body(envelope)
        with pytest.raises(WhopError, match="data object"):
            WhopProvider().verify_webhook(_headers(body), body)

    def test_blank_secret_raises_not_configured(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "whop_webhook_secret", "")
        body = _body(_envelope(_ORDER))
        with pytest.raises(WhopNotConfigured):
            WhopProvider().verify_webhook(_headers(body), body)

    def test_blank_api_key_does_not_matter_for_verification(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "whop_api_key", "")
        body = _body(_envelope(_ORDER))
        assert WhopProvider().verify_webhook(_headers(body), body).event_type == "payment.succeeded"


# ---------------------------------------------------------------------------
# handle_event
# ---------------------------------------------------------------------------


class TestHandleEvent:
    def test_paid_marks_order_paid_and_returns_order_id(self, db, monkeypatch):
        order, payment = _make_order_and_payment(db)
        client = _install(monkeypatch, _FakeClient(get=_fresh(order)))

        result = WhopProvider().handle_event(db, _verified(_envelope(order)))

        db.flush()
        db.refresh(order)
        db.refresh(payment)
        assert result == order.id
        assert order.status == "PAID"
        assert payment.status == "succeeded"
        assert payment.provider == "whop"
        assert payment.provider_payment_id == _PAY_ID
        assert payment.provider_data["checkout_url"].endswith(_CONFIG_ID)
        assert payment.provider_data["payment_id"] == _PAY_ID
        assert payment.provider_data["card_last4"] == "4242"
        assert payment.provider_data["paid_total"] == 129.0
        assert _payment_event_types(db, payment.id) == ["payment.confirmed", "payment.succeeded"]
        assert "awaiting_manual_fulfillment" in _order_event_types(db, order.id)
        assert _mismatch_events(db, order.id) == []
        # Re-confirmed with Whop before moving money-state, Bearer auth, pinned.
        assert [c[0] for c in client.calls] == ["get"]
        assert client.calls[0][1] == f"{_BASE}/payments/{_PAY_ID}"
        assert client.calls[0][2]["headers"]["Authorization"] == f"Bearer {_KEY}"
        assert client.calls[0][2]["headers"]["Api-Version-Date"] == _PIN

    def test_paid_resolves_row_by_pay_id_when_already_stamped(self, db, monkeypatch):
        order, payment = _make_order_and_payment(db, provider_payment_id=_PAY_ID)
        _install(monkeypatch, _FakeClient(get=_fresh(order)))
        assert WhopProvider().handle_event(db, _verified(_envelope(order, config_id="ch_unknown"))) == order.id
        db.refresh(payment)
        assert payment.status == "succeeded"

    def test_paid_resolves_by_order_number_when_ids_unknown(self, db, monkeypatch):
        # A degraded checkout never recorded a ch_ id; the metadata still
        # names the order.
        order, payment = _make_order_and_payment(db, provider_payment_id=None)
        _install(monkeypatch, _FakeClient(get=_fresh(order)))
        assert WhopProvider().handle_event(db, _verified(_envelope(order, config_id="ch_unknown"))) == order.id
        db.refresh(order)
        db.refresh(payment)
        assert order.status == "PAID"
        assert payment.provider_payment_id == _PAY_ID

    def test_paid_refetch_status_succeeded_accepted(self, db, monkeypatch):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_fresh(order, status="succeeded", substatus=None)))
        assert WhopProvider().handle_event(db, _verified(_envelope(order))) == order.id

    def test_paid_refetch_substatus_succeeded_accepted(self, db, monkeypatch):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_fresh(order, status="open", substatus="succeeded")))
        assert WhopProvider().handle_event(db, _verified(_envelope(order))) == order.id

    def test_paid_but_refetch_says_open_raises_and_leaves_pending(self, db, monkeypatch):
        order, payment = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_fresh(order, status="open", substatus="pending")))
        with pytest.raises(WhopError, match="not paid"):
            WhopProvider().handle_event(db, _verified(_envelope(order)))
        db.refresh(order)
        db.refresh(payment)
        assert order.status == "PAYMENT_PENDING"
        assert payment.status == "pending"
        assert _payment_event_types(db, payment.id) == []

    def test_paid_refetch_network_error_raises(self, db, monkeypatch):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get_raises=httpx.ConnectError("boom")))
        with pytest.raises(WhopError, match="lookup"):
            WhopProvider().handle_event(db, _verified(_envelope(order)))
        db.refresh(order)
        assert order.status == "PAYMENT_PENDING"

    def test_paid_refetch_http_500_raises(self, db, monkeypatch):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_FakeResponse(500, None, "server error")))
        with pytest.raises(WhopError, match="500"):
            WhopProvider().handle_event(db, _verified(_envelope(order)))

    def test_paid_refetch_non_json_raises(self, db, monkeypatch):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_FakeResponse(200, None, "<html>")))
        with pytest.raises(WhopError, match="non-JSON"):
            WhopProvider().handle_event(db, _verified(_envelope(order)))

    def test_paid_refetch_without_payment_object_raises(self, db, monkeypatch):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_FakeResponse(200, {"data": {"status": "paid"}})))
        with pytest.raises(WhopError, match="no payment object"):
            WhopProvider().handle_event(db, _verified(_envelope(order)))

    def test_paid_without_api_key_raises_not_configured_and_leaves_pending(self, db, monkeypatch):
        monkeypatch.setattr(get_settings(), "whop_api_key", "")
        order, _ = _make_order_and_payment(db)
        with pytest.raises(WhopNotConfigured):
            WhopProvider().handle_event(db, _verified(_envelope(order)))
        db.refresh(order)
        assert order.status == "PAYMENT_PENDING"

    def test_paid_amount_as_money_object_accepted(self, db, monkeypatch):
        order, payment = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_fresh(order, shape="object")))
        assert WhopProvider().handle_event(db, _verified(_envelope(order, shape="object"))) == order.id
        db.refresh(payment)
        assert payment.provider_data["paid_total"] == 129.0
        assert _mismatch_events(db, order.id) == []

    def test_paid_amount_as_numeric_string_accepted(self, db, monkeypatch):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_fresh(order, shape="string")))
        assert WhopProvider().handle_event(db, _verified(_envelope(order, shape="string"))) == order.id
        assert _mismatch_events(db, order.id) == []

    def test_paid_amount_falls_back_to_usd_total_then_subtotal(self, db, monkeypatch):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_fresh(order, total=None, usd_total=129.0)))
        assert WhopProvider().handle_event(db, _verified(_envelope(order))) == order.id
        assert _mismatch_events(db, order.id) == []

        order2, _ = _make_order_and_payment(db, provider_payment_id=_CONFIG_ID_2)
        _install(monkeypatch, _FakeClient(get=_fresh(order2, pay_id="pay_test_whop_sub", total=None, subtotal=129.0)))
        event = _verified(_envelope(order2, pay_id="pay_test_whop_sub", config_id=_CONFIG_ID_2, msg_id="msg_test_whop_sub"))
        assert WhopProvider().handle_event(db, event) == order2.id

    def test_underpaid_blocks_sets_underpaid_and_records_mismatch(self, db, monkeypatch):
        order, payment = _make_order_and_payment(db, total_cents=12900)
        _install(monkeypatch, _FakeClient(get=_fresh(order, total=100.0)))

        assert WhopProvider().handle_event(db, _verified(_envelope(order, total=100.0))) is None

        db.refresh(order)
        db.refresh(payment)
        assert order.status == "PAYMENT_PENDING"
        assert payment.status == "underpaid"
        assert payment.provider_payment_id == _CONFIG_ID
        (mismatch,) = _mismatch_events(db, order.id)
        assert mismatch["reason"] == "underpaid"
        assert mismatch["paid_cents"] == 10000
        assert mismatch["expected_cents"] == 12900
        assert mismatch["payment_id"] == _PAY_ID
        assert _payment_event_types(db, payment.id) == ["payment.succeeded"]

    def test_overpaid_marks_paid_and_records_mismatch(self, db, monkeypatch):
        order, payment = _make_order_and_payment(db, total_cents=12900)
        _install(monkeypatch, _FakeClient(get=_fresh(order, total=140.0)))
        assert WhopProvider().handle_event(db, _verified(_envelope(order, total=140.0))) == order.id
        db.refresh(order)
        db.refresh(payment)
        assert order.status == "PAID"
        assert payment.status == "succeeded"
        (mismatch,) = _mismatch_events(db, order.id)
        assert mismatch["reason"] == "overpaid"
        assert mismatch["paid_cents"] == 14000

    def test_currency_mismatch_blocks(self, db, monkeypatch):
        order, payment = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_fresh(order, shape="object", currency="eur")))
        assert WhopProvider().handle_event(db, _verified(_envelope(order))) is None
        db.refresh(order)
        db.refresh(payment)
        assert order.status == "PAYMENT_PENDING"
        assert payment.status == "underpaid"
        (mismatch,) = _mismatch_events(db, order.id)
        assert mismatch["reason"] == "currency"
        assert mismatch["currency"] == "eur"

    def test_unreadable_amount_blocks(self, db, monkeypatch):
        order, payment = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_fresh(order, total=None)))
        assert WhopProvider().handle_event(db, _verified(_envelope(order, total=None))) is None
        db.refresh(payment)
        assert payment.status == "underpaid"
        (mismatch,) = _mismatch_events(db, order.id)
        assert mismatch["reason"] == "unreadable"
        assert mismatch["paid_cents"] is None

    def test_amount_from_refetch_wins_over_webhook_body(self, db, monkeypatch):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_fresh(order, total=129.0)))
        # The webhook body says 1.00; Whop's own record says 129.00.
        assert WhopProvider().handle_event(db, _verified(_envelope(order, total=1.0))) == order.id
        assert _mismatch_events(db, order.id) == []

    def test_webhook_amount_used_when_refetch_has_none(self, db, monkeypatch):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_fresh(order, total=None)))
        assert WhopProvider().handle_event(db, _verified(_envelope(order, total=129.0))) == order.id

    def test_already_paid_order_is_noop_without_refetch(self, db):
        order, payment = _make_order_and_payment(db)
        payment_services.mark_order_paid(db, order_id=order.id, provider="whop", provider_payment_id=_PAY_ID, source="admin:test")
        # No GET either: the order is resolved before Whop is asked.
        assert WhopProvider().handle_event(db, _verified(_envelope(order))) is None
        db.refresh(order)
        assert order.status == "PAID"
        assert _payment_event_types(db, payment.id) == ["payment.confirmed"]

    def test_failed_sets_payment_failed_order_stays_pending(self, db):
        order, payment = _make_order_and_payment(db)
        event = _verified(_envelope(order, event_type="payment.failed", status="open", substatus="failed", failure_message="card_declined", decline_code="insufficient_funds"))
        assert WhopProvider().handle_event(db, event) is None
        db.refresh(order)
        db.refresh(payment)
        assert order.status == "PAYMENT_PENDING"
        assert payment.status == "failed"
        assert _payment_event_types(db, payment.id) == ["payment.failed"]
        row = db.execute(text("SELECT data FROM payment_events WHERE payment_id = :pid"), {"pid": payment.id}).one()
        assert row[0]["decline_code"] == "insufficient_funds"
        assert row[0]["failure_message"] == "card_declined"

    def test_canceled_sets_failed(self, db):
        order, payment = _make_order_and_payment(db)
        assert WhopProvider().handle_event(db, _verified(_envelope(order, event_type="payment.canceled", status="void", substatus="canceled"))) is None
        db.refresh(payment)
        assert payment.status == "failed"

    def test_pending_sets_processing(self, db):
        order, payment = _make_order_and_payment(db)
        assert WhopProvider().handle_event(db, _verified(_envelope(order, event_type="payment.pending", status="pending", substatus="pending"))) is None
        db.refresh(order)
        db.refresh(payment)
        assert order.status == "PAYMENT_PENDING"
        assert payment.status == "processing"

    def test_authorized_sets_processing(self, db):
        order, payment = _make_order_and_payment(db)
        assert WhopProvider().handle_event(db, _verified(_envelope(order, event_type="payment.authorized", status="authorized", substatus="requires_capture"))) is None
        db.refresh(payment)
        assert payment.status == "processing"

    def test_refund_created_records_only(self, db):
        order, payment = _make_order_and_payment(db)
        assert WhopProvider().handle_event(db, _verified(_envelope(order, event_type="refund.created", substatus="refunded"))) is None
        db.refresh(payment)
        assert payment.status == "pending"
        assert _payment_event_types(db, payment.id) == ["refund.created"]

    def test_unknown_event_records_only(self, db):
        order, payment = _make_order_and_payment(db)
        assert WhopProvider().handle_event(db, _verified(_envelope(order, event_type="dispute.created"))) is None
        db.refresh(payment)
        assert payment.status == "pending"
        assert _payment_event_types(db, payment.id) == ["dispute.created"]

    def test_order_number_mismatch_refuses(self, db):
        order, payment = _make_order_and_payment(db)
        assert WhopProvider().handle_event(db, _verified(_envelope(order, order_number="PEN-OTHER1"))) is None
        db.refresh(order)
        db.refresh(payment)
        assert order.status == "PAYMENT_PENDING"
        assert payment.status == "pending"
        assert _payment_event_types(db, payment.id) == []

    def test_unknown_payment_and_order_ignored(self, db):
        order, _ = _make_order_and_payment(db)
        event = _verified(_envelope(order, pay_id="pay_nobody", config_id="ch_nobody", order_number="PEN-NOBODY"))
        assert WhopProvider().handle_event(db, event) is None
        db.refresh(order)
        assert order.status == "PAYMENT_PENDING"

    def test_non_paid_event_never_downgrades_succeeded_row(self, db, monkeypatch):
        order, payment = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(get=_fresh(order)))
        WhopProvider().handle_event(db, _verified(_envelope(order)))
        late = _verified(_envelope(order, event_type="payment.failed", msg_id="msg_test_whop_late"))
        assert WhopProvider().handle_event(db, late) is None
        db.refresh(payment)
        assert payment.status == "succeeded"
        # Same transaction, same created_at: compare as a set of types.
        assert sorted(_payment_event_types(db, payment.id)) == ["payment.confirmed", "payment.failed", "payment.succeeded"]

    def test_paid_on_superseded_row_marks_that_row_and_supersedes_newer_pending(self, db, monkeypatch):
        order, old_payment = _make_order_and_payment(db, payment_status="superseded")
        new_payment = Payment(
            order_id=order.id,
            provider="whop",
            provider_payment_id=_CONFIG_ID_2,
            status="pending",
            amount_cents=order.total_cents,
            currency="usd",
        )
        db.add(new_payment)
        db.flush()
        _install(monkeypatch, _FakeClient(get=_fresh(order)))

        assert WhopProvider().handle_event(db, _verified(_envelope(order))) == order.id

        db.flush()
        db.refresh(order)
        db.refresh(old_payment)
        db.refresh(new_payment)
        assert order.status == "PAID"
        assert old_payment.status == "succeeded"
        assert old_payment.provider_payment_id == _PAY_ID
        assert new_payment.status == "superseded"
        assert new_payment.provider_payment_id == _CONFIG_ID_2

    def test_paid_event_without_data_id_raises(self, db):
        order, _ = _make_order_and_payment(db)
        with pytest.raises(WhopError, match="without a payment id"):
            WhopProvider().handle_event(db, _verified(_envelope(order, pay_id="")))


# ---------------------------------------------------------------------------
# create_payment_instructions (network mocked)
# ---------------------------------------------------------------------------


class TestCreatePaymentInstructions:
    def test_no_key_raises_not_configured(self, monkeypatch, db):
        monkeypatch.setattr(get_settings(), "whop_api_key", "")
        order, _ = _make_order_and_payment(db)
        with pytest.raises(WhopNotConfigured, match="WHOP_API_KEY"):
            WhopProvider().create_payment_instructions(order)

    def test_blank_site_url_raises_not_configured_without_http(self, monkeypatch, db):
        monkeypatch.setattr(get_settings(), "public_site_url", "")
        order, _ = _make_order_and_payment(db)
        with pytest.raises(WhopNotConfigured, match="PUBLIC_SITE_URL"):
            WhopProvider().create_payment_instructions(order)

    def test_non_http_site_url_raises_not_configured(self, monkeypatch, db):
        monkeypatch.setattr(get_settings(), "public_site_url", "ftp://files.example.test")
        order, _ = _make_order_and_payment(db)
        with pytest.raises(WhopNotConfigured, match="PUBLIC_SITE_URL"):
            WhopProvider().create_payment_instructions(order)

    def test_http_site_url_allowed_for_local_dev(self, monkeypatch, db):
        monkeypatch.setattr(get_settings(), "public_site_url", "http://localhost:3010/")
        order, _ = _make_order_and_payment(db)
        client = _install(monkeypatch, _FakeClient(post=_created()))
        WhopProvider().create_payment_instructions(order)
        assert client.calls[0][2]["json"]["redirect_url"] == f"http://localhost:3010/order/{order.access_token}"

    def test_unknown_environment_raises(self, monkeypatch, db):
        monkeypatch.setattr(get_settings(), "whop_environment", "staging")
        order, _ = _make_order_and_payment(db)
        with pytest.raises(WhopError, match="WHOP_ENVIRONMENT"):
            WhopProvider().create_payment_instructions(order)

    def test_request_shape(self, monkeypatch, db):
        order, _ = _make_order_and_payment(db, total_cents=1250)
        client = _install(monkeypatch, _FakeClient(post=_created()))

        instructions = WhopProvider().create_payment_instructions(order)

        assert [c[0] for c in client.calls] == ["post"]
        _, url, call = client.calls[0]
        assert url == f"{_BASE}/checkout_configurations"
        assert call["headers"]["Authorization"] == f"Bearer {_KEY}"
        assert call["headers"]["Api-Version-Date"] == _PIN
        assert call["headers"]["Content-Type"] == "application/json"
        body = call["json"]
        assert body["mode"] == "payment"
        assert body["plan"]["title"] == f"Order {order.public_order_number}"
        assert len(body["plan"]["title"]) <= 30
        assert body["plan"]["plan_type"] == "one_time"
        assert body["plan"]["initial_price"] == pytest.approx(12.5, abs=0.001)
        assert body["plan"]["currency"] == "usd"
        assert body["metadata"] == {"order_number": order.public_order_number}
        assert body["redirect_url"] == f"{_SITE}/order/{order.access_token}"
        assert "account_id" not in body
        # Compliance: only the order number and amount leave the building.
        dumped = json.dumps(body).lower()
        assert "peptide" not in dumped
        assert _TEST_EMAIL not in dumped
        assert "card buyer" not in dumped

        assert instructions.provider == "whop"
        assert instructions.summary == "Pay by card or Apple Pay"
        assert instructions.details["provider_payment_id"] == _CONFIG_ID
        assert instructions.details["checkout_configuration_id"] == _CONFIG_ID
        assert instructions.details["checkout_url"] == f"https://whop.com/checkout/plan_test_000001/?session={_CONFIG_ID}"
        assert instructions.details["usd_total_cents"] == 1250
        assert instructions.details["plan_id"] == "plan_test_000001"

    def test_account_id_sent_only_when_configured(self, monkeypatch, db):
        monkeypatch.setattr(get_settings(), "whop_account_id", " biz_test_0001 ")
        order, _ = _make_order_and_payment(db)
        client = _install(monkeypatch, _FakeClient(post=_created()))
        WhopProvider().create_payment_instructions(order)
        assert client.calls[0][2]["json"]["account_id"] == "biz_test_0001"

    def test_api_version_header_omitted_when_blank(self, monkeypatch, db):
        monkeypatch.setattr(get_settings(), "whop_api_version_date", "")
        order, _ = _make_order_and_payment(db)
        client = _install(monkeypatch, _FakeClient(post=_created()))
        WhopProvider().create_payment_instructions(order)
        assert "Api-Version-Date" not in client.calls[0][2]["headers"]

    def test_live_environment_uses_production_base(self, monkeypatch, db):
        monkeypatch.setattr(get_settings(), "whop_environment", "live")
        order, _ = _make_order_and_payment(db)
        client = _install(monkeypatch, _FakeClient(post=_created()))
        WhopProvider().create_payment_instructions(order)
        assert client.calls[0][1] == "https://api.whop.com/api/v1/checkout_configurations"

    @pytest.mark.parametrize("status", [200, 201])
    def test_200_and_201_accepted(self, monkeypatch, db, status):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(post=_created(status=status)))
        assert WhopProvider().create_payment_instructions(order).details["provider_payment_id"] == _CONFIG_ID

    def test_response_wrapped_in_data_accepted(self, monkeypatch, db):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(post=_created(wrapped=True)))
        assert WhopProvider().create_payment_instructions(order).details["checkout_url"].startswith("https://whop.com/")

    def test_plan_id_none_when_absent(self, monkeypatch, db):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(post=_created(plan_id=None, purchase_url="https://whop.com/checkout/x")))
        assert WhopProvider().create_payment_instructions(order).details["plan_id"] is None

    def test_http_error_raises(self, monkeypatch, db):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(post=_FakeResponse(400, {"error": "bad"}, '{"error":"bad"}')))
        with pytest.raises(WhopError, match="400"):
            WhopProvider().create_payment_instructions(order)

    def test_network_error_raises(self, monkeypatch, db):
        order, _ = _make_order_and_payment(db)

        class _Boom(_FakeClient):
            def post(self, url, headers=None, json=None):
                raise httpx.ConnectError("boom")

        _install(monkeypatch, _Boom())
        with pytest.raises(WhopError, match="creation failed"):
            WhopProvider().create_payment_instructions(order)

    def test_non_json_raises(self, monkeypatch, db):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(post=_FakeResponse(201, None, "<html>")))
        with pytest.raises(WhopError, match="not JSON"):
            WhopProvider().create_payment_instructions(order)

    def test_missing_purchase_url_raises(self, monkeypatch, db):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(post=_FakeResponse(201, {"id": _CONFIG_ID})))
        with pytest.raises(WhopError, match="purchase_url"):
            WhopProvider().create_payment_instructions(order)

    def test_missing_id_raises(self, monkeypatch, db):
        order, _ = _make_order_and_payment(db)
        _install(monkeypatch, _FakeClient(post=_FakeResponse(201, {"purchase_url": "https://whop.com/checkout/x"})))
        with pytest.raises(WhopError, match="configuration id"):
            WhopProvider().create_payment_instructions(order)
