"""End-to-end: a signed Whop webhook through POST
/api/v1/webhooks/payments/whop with the real provider, real DB and the
route's idempotency guard (app/api/webhooks.py)."""

from __future__ import annotations

import json
import time
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
from app.payments import whop
from app.payments.whop import compute_signature
from app.services import order_paid

_TEST_EMAIL = "whop-route-test@example.invalid"
_KEY = "test-whop-route-key"
_SECRET = "ws_test_route_secret_0000000000000000"
_CONFIG_ID = "ch_test_route_000000000001"
_PAY_ID = "pay_test_route_000000000001"
_MSG_PREFIX = "msg_test_route_"
_URL = "/api/v1/webhooks/payments/whop"


def _cleanup(session):
    session.execute(
        text("DELETE FROM webhook_events WHERE source = 'whop' AND external_id LIKE :p"), {"p": f"{_MSG_PREFIX}%"}
    )
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
        session.execute(text("DELETE FROM orders WHERE id = ANY(:ids)"), {"ids": ids})
    session.execute(
        text("DELETE FROM payments WHERE provider_payment_id = ANY(:pids)"), {"pids": [_CONFIG_ID, _PAY_ID]}
    )
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
    monkeypatch.setattr(settings, "whop_api_key", _KEY)
    monkeypatch.setattr(settings, "whop_webhook_secret", _SECRET)
    monkeypatch.setattr(settings, "whop_environment", "sandbox")
    monkeypatch.setattr(settings, "fulfillment_mode", "manual")


@pytest.fixture
def fanout_calls(monkeypatch):
    calls: list[uuid.UUID] = []
    monkeypatch.setattr(order_paid, "run_order_paid_fanout", lambda order_id: calls.append(order_id))
    return calls


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


class _Client:
    """What GET /payments/{id} answers on the paid re-check."""

    def __init__(self, status="paid", substatus="succeeded", total=129.0, raises=None):
        self._status = status
        self._substatus = substatus
        self._total = total
        self._raises = raises

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return None

    def get(self, url, headers=None):
        if self._raises:
            raise self._raises
        return _Response(
            200,
            {
                "id": _PAY_ID,
                "status": self._status,
                "substatus": self._substatus,
                "total": self._total,
                "currency": "usd",
                "card_brand": "visa",
                "card_last4": "4242",
            },
        )


def _make_order(session) -> Order:
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
            provider="whop",
            provider_payment_id=_CONFIG_ID,
            status="pending",
            amount_cents=12900,
            currency="usd",
            provider_data={"checkout_url": f"https://whop.com/checkout/plan_x/?session={_CONFIG_ID}"},
        )
    )
    session.commit()
    return order


def _body(
    order: Order,
    event_type: str = "payment.succeeded",
    *,
    total: float = 129.0,
    msg_id: str = f"{_MSG_PREFIX}1",
    pay_id: str = _PAY_ID,
    config_id: str = _CONFIG_ID,
    order_number: str | None = None,
) -> bytes:
    return json.dumps(
        {
            "id": msg_id,
            "type": event_type,
            "api_version": "v1",
            "data": {
                "id": pay_id,
                "status": "paid" if event_type == "payment.succeeded" else "open",
                "substatus": "succeeded" if event_type == "payment.succeeded" else "pending",
                "total": total,
                "currency": "usd",
                "checkout_configuration_id": config_id,
                "metadata": {"order_number": order_number or order.public_order_number},
            },
        }
    ).encode()


def _headers(body: bytes, *, msg_id: str = f"{_MSG_PREFIX}1", secret: str = _SECRET, ts=None, signature=None) -> dict:
    ts = int(time.time()) if ts is None else ts
    return {
        "Content-Type": "application/json",
        "webhook-id": msg_id,
        "webhook-timestamp": str(ts),
        "webhook-signature": signature if signature is not None else compute_signature(secret, msg_id, ts, body),
    }


def _webhook_rows(session) -> int:
    return session.execute(
        text("SELECT count(*) FROM webhook_events WHERE source = 'whop' AND external_id LIKE :p"),
        {"p": f"{_MSG_PREFIX}%"},
    ).scalar_one()


def _payment_status(session, order: Order) -> str:
    return session.execute(
        text("SELECT status FROM payments WHERE order_id = :oid ORDER BY created_at DESC LIMIT 1"), {"oid": order.id}
    ).scalar_one()


def test_signed_paid_webhook_marks_order_paid_and_schedules_fanout(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    monkeypatch.setattr(whop, "_client", lambda: _Client())
    client = TestClient(app)
    body = _body(order)

    response = client.post(_URL, content=body, headers=_headers(body))

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    session.expire_all()
    assert session.get(Order, order.id).status == "PAID"
    assert _payment_status(session, order) == "succeeded"
    assert fanout_calls == [order.id]
    assert _webhook_rows(session) == 1


def test_duplicate_delivery_same_webhook_id_returns_already_processed(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    monkeypatch.setattr(whop, "_client", lambda: _Client())
    client = TestClient(app)
    body = _body(order)

    first = client.post(_URL, content=body, headers=_headers(body))
    second = client.post(_URL, content=body, headers=_headers(body))

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
    monkeypatch.setattr(whop, "_client", lambda: (_ for _ in ()).throw(AssertionError("no HTTP")))
    client = TestClient(app)
    body = _body(order)

    response = client.post(_URL, content=body, headers=_headers(body, signature="v1,ZGVhZGJlZWY="))

    assert response.status_code == 400
    assert "verification failed" in response.json()["detail"].lower()
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert _webhook_rows(session) == 0
    assert fanout_calls == []


def test_missing_signature_headers_returns_400(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    monkeypatch.setattr(whop, "_client", lambda: (_ for _ in ()).throw(AssertionError("no HTTP")))
    body = _body(order)
    response = TestClient(app).post(_URL, content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert "webhook-signature" in response.json()["detail"]
    assert _webhook_rows(session) == 0
    assert fanout_calls == []


def test_stale_timestamp_returns_400(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    monkeypatch.setattr(whop, "_client", lambda: (_ for _ in ()).throw(AssertionError("no HTTP")))
    body = _body(order)
    response = TestClient(app).post(_URL, content=body, headers=_headers(body, ts=1_000_000_000))
    assert response.status_code == 400
    assert "tolerance" in response.json()["detail"]
    assert _webhook_rows(session) == 0


def test_blank_secret_returns_400(session, monkeypatch, fanout_calls):
    monkeypatch.setattr(get_settings(), "whop_webhook_secret", "")
    order = _make_order(session)
    body = _body(order)
    response = TestClient(app).post(_URL, content=body, headers=_headers(body))
    assert response.status_code == 400
    assert "WHOP_WEBHOOK_SECRET" in response.json()["detail"]
    assert _webhook_rows(session) == 0


def test_pending_then_paid_are_two_events(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    monkeypatch.setattr(whop, "_client", lambda: _Client())
    client = TestClient(app)

    pending = _body(order, "payment.pending", msg_id=f"{_MSG_PREFIX}pending")
    assert client.post(_URL, content=pending, headers=_headers(pending, msg_id=f"{_MSG_PREFIX}pending")).json() == {
        "status": "processed"
    }
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert _payment_status(session, order) == "processing"
    assert fanout_calls == []

    paid = _body(order, msg_id=f"{_MSG_PREFIX}paid")
    assert client.post(_URL, content=paid, headers=_headers(paid, msg_id=f"{_MSG_PREFIX}paid")).json() == {
        "status": "processed"
    }
    session.expire_all()
    assert session.get(Order, order.id).status == "PAID"
    assert fanout_calls == [order.id]
    assert _webhook_rows(session) == 2


def test_paid_when_refetch_fails_returns_500_and_commits_nothing(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    monkeypatch.setattr(whop, "_client", lambda: _Client(raises=httpx.ConnectError("boom")))
    client = TestClient(app, raise_server_exceptions=False)
    body = _body(order)

    response = client.post(_URL, content=body, headers=_headers(body))

    assert response.status_code == 500
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert _webhook_rows(session) == 0  # so Whop's retry gets a clean attempt
    assert fanout_calls == []


def test_paid_when_whop_disagrees_returns_500_and_commits_nothing(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    monkeypatch.setattr(whop, "_client", lambda: _Client(status="open", substatus="pending"))
    client = TestClient(app, raise_server_exceptions=False)
    body = _body(order)

    response = client.post(_URL, content=body, headers=_headers(body))

    assert response.status_code == 500
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert _webhook_rows(session) == 0
    assert fanout_calls == []


def test_underpaid_acknowledged_200_without_paying(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    monkeypatch.setattr(whop, "_client", lambda: _Client(total=50.0))
    body = _body(order, total=50.0)

    response = TestClient(app).post(_URL, content=body, headers=_headers(body))

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert _payment_status(session, order) == "underpaid"
    assert fanout_calls == []
    assert _webhook_rows(session) == 1
    mismatch = session.execute(
        text("SELECT count(*) FROM order_events WHERE order_id = :oid AND event_type = 'payment_amount_mismatch'"),
        {"oid": order.id},
    ).scalar_one()
    assert mismatch == 1


def test_unknown_order_acknowledged_200(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    monkeypatch.setattr(whop, "_client", lambda: (_ for _ in ()).throw(AssertionError("no HTTP")))
    body = _body(order, pay_id="pay_nobody", config_id="ch_nobody", order_number="PEN-NOBODY")

    response = TestClient(app).post(_URL, content=body, headers=_headers(body))

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert fanout_calls == []
    assert _webhook_rows(session) == 1


def test_unregistered_event_type_recorded_200(session, monkeypatch, fanout_calls):
    order = _make_order(session)
    monkeypatch.setattr(whop, "_client", lambda: (_ for _ in ()).throw(AssertionError("no HTTP")))
    body = _body(order, "dispute.created")

    response = TestClient(app).post(_URL, content=body, headers=_headers(body))

    assert response.status_code == 200
    session.expire_all()
    assert session.get(Order, order.id).status == "PAYMENT_PENDING"
    assert _payment_status(session, order) == "pending"
    assert fanout_calls == []
    recorded = session.execute(
        text(
            "SELECT count(*) FROM payment_events WHERE event_type = 'dispute.created' "
            "AND payment_id IN (SELECT id FROM payments WHERE order_id = :oid)"
        ),
        {"oid": order.id},
    ).scalar_one()
    assert recorded == 1
