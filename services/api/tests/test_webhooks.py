from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal
from app.main import app
from app.payments import registry
from app.payments.base import VerifiedEvent

_TEST_SOURCE = "test-provider"
_TEST_EXTERNAL_ID = "evt_test_123"


class _FakeProvider:
    """Registered into app.payments.registry only for the duration of
    this test — verifies nothing (always succeeds) and just counts how
    many times handle_event actually ran, so the test can assert the
    webhook route's idempotency guard (WebhookEvent's UNIQUE(source,
    external_id)) prevents a second call on a retried delivery."""

    provider_key = _TEST_SOURCE

    def __init__(self):
        self.handle_event_calls = 0

    def create_payment_instructions(self, order):  # pragma: no cover - unused by this test
        raise NotImplementedError

    def verify_webhook(self, headers, raw_body):
        return VerifiedEvent(external_id=_TEST_EXTERNAL_ID, event_type="test.event", order_id=None, raw={"ok": True})

    def handle_event(self, session, event):
        self.handle_event_calls += 1


def _cleanup(session):
    session.execute(text("DELETE FROM webhook_events WHERE source = :source"), {"source": _TEST_SOURCE})
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
def fake_provider():
    provider = _FakeProvider()
    registry._PROVIDERS[_TEST_SOURCE] = provider
    yield provider
    del registry._PROVIDERS[_TEST_SOURCE]


def test_unregistered_provider_returns_501():
    client = TestClient(app)
    response = client.post("/api/v1/webhooks/payments/some-vendor-nobody-registered", json={})
    assert response.status_code == 501


def test_webhook_idempotency_processes_a_retried_event_only_once(session, fake_provider):
    client = TestClient(app)

    first = client.post(f"/api/v1/webhooks/payments/{_TEST_SOURCE}", json={"any": "payload"})
    assert first.status_code == 200
    assert first.json() == {"status": "processed"}

    second = client.post(f"/api/v1/webhooks/payments/{_TEST_SOURCE}", json={"any": "payload"})
    assert second.status_code == 200
    assert second.json() == {"status": "already_processed"}

    assert fake_provider.handle_event_calls == 1

    rows = session.execute(
        text("SELECT count(*) FROM webhook_events WHERE source = :source AND external_id = :external_id"),
        {"source": _TEST_SOURCE, "external_id": _TEST_EXTERNAL_ID},
    ).scalar_one()
    assert rows == 1
