from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text

from worker.alliancetek.client import SupplierApiConfigError, SupplierApiError
from worker.alliancetek.errors import RETRY_DELAYS_SECONDS
from worker.config import get_settings
from worker.db import order_events_table, order_items_table, orders_table, supplier_attempts_table, supplier_orders_table
from worker.jobs import submit_supplier_order
from worker.order_status import OrderStatus, SupplierOrderStatus
from worker.queue.local import LocalQueueProvider, background_jobs_table

_TEST_EMAIL = "test-worker-jobs@example.invalid"
_SHIPPING_ADDRESS = {
    "line1": "1 Test St",
    "line2": None,
    "city": "Testville",
    "region": "CA",
    "postal_code": "90210",
    "country": "US",
}


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://sandbox.example.invalid/orders")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"status {status_code}", request=request, response=response)


def _supplier_api_error(*, status_code: int | None = None, cause: Exception | None = None) -> SupplierApiError:
    """Builds a SupplierApiError with __cause__ set the way
    AllianceTekClient._request actually raises it (`raise
    SupplierApiError(...) from last_error`) — classify_supplier_error
    unwraps __cause__, so tests need the same shape."""
    err = SupplierApiError("simulated failure")
    err.__cause__ = cause if cause is not None else _http_status_error(status_code or 500)
    return err


class _FakeAllianceTekClient:
    """Stub standing in for AllianceTekClient — see
    test_alliancetek_client.py for real-client behavior; this test file
    is about submit_supplier_order's retry/classification/DB logic."""

    def __init__(self, *, errors: list[Exception] | None = None, response: dict | None = None):
        self.calls: list[dict] = []
        self._errors = list(errors) if errors else []
        self._response = response if response is not None else {"result": {"orderId": 1}}

    def create_update_order(self, payload: dict) -> dict:
        self.calls.append(payload)
        if self._errors:
            raise self._errors.pop(0)
        return self._response


@pytest.fixture
def engine():
    eng = create_engine(get_settings().database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def queue(engine):
    return LocalQueueProvider(engine)


@pytest.fixture
def order_id(engine):
    """Builds a minimal product/variant/order/order_item row set via raw
    SQL / worker's own hand-mirrored Core tables — worker has no ORM for
    api's tables (see worker/db.py), so the fixture writes exactly the
    columns a real submit_supplier_order job would read.
    """
    product_id = uuid.uuid4()
    variant_id = uuid.uuid4()
    order = uuid.uuid4()
    item_id = uuid.uuid4()
    public_order_number = f"TCP-TST{uuid.uuid4().hex[:6].upper()}"

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO products (id, slug, name) VALUES (:id, :slug, :name)"),
            {"id": product_id, "slug": f"test-worker-jobs-{product_id}", "name": "Test Product"},
        )
        conn.execute(
            text(
                "INSERT INTO product_variants (id, product_id, sku, name, retail_price_cents) "
                "VALUES (:id, :product_id, :sku, :name, :price)"
            ),
            {
                "id": variant_id,
                "product_id": product_id,
                "sku": f"TEST-{variant_id}",
                "name": "Test Variant",
                "price": 1999,
            },
        )
        conn.execute(
            sa.insert(orders_table).values(
                id=order,
                public_order_number=public_order_number,
                access_token=f"test-token-{order}",
                customer_email=_TEST_EMAIL,
                status=OrderStatus.PAYMENT_PENDING,
                currency="usd",
                shipping_address=_SHIPPING_ADDRESS,
                subtotal_cents=1999,
                shipping_cents=0,
                tax_cents=0,
                total_cents=1999,
            )
        )
        conn.execute(
            sa.insert(order_items_table).values(
                id=item_id,
                order_id=order,
                product_variant_id=variant_id,
                sku_snapshot="TC-TEST-SKU",
                display_name_at_purchase="Test Variant",
                supplier_product_id_at_purchase=999999,
                supplier_sku_at_purchase="SUP-SKU-1",
                supplier_name_at_purchase="Supplier Test Product",
                quantity=1,
                unit_price_cents=1999,
                total_price_cents=1999,
            )
        )

    yield order

    with engine.begin() as conn:
        conn.execute(sa.delete(background_jobs_table).where(background_jobs_table.c.payload["order_id"].astext == str(order)))
        conn.execute(order_events_table.delete().where(order_events_table.c.order_id == order))
        conn.execute(
            sa.delete(supplier_attempts_table).where(
                supplier_attempts_table.c.supplier_order_id.in_(
                    sa.select(supplier_orders_table.c.id).where(supplier_orders_table.c.order_id == order)
                )
            )
        )
        conn.execute(sa.delete(supplier_orders_table).where(supplier_orders_table.c.order_id == order))
        conn.execute(sa.delete(order_items_table).where(order_items_table.c.order_id == order))
        conn.execute(sa.delete(orders_table).where(orders_table.c.id == order))
        conn.execute(text("DELETE FROM product_variants WHERE id = :id"), {"id": variant_id})
        conn.execute(text("DELETE FROM products WHERE id = :id"), {"id": product_id})


def _public_order_number(engine, order_id) -> str:
    with engine.connect() as conn:
        return conn.execute(
            sa.select(orders_table.c.public_order_number).where(orders_table.c.id == order_id)
        ).scalar_one()


def _order_status(engine, order_id) -> str:
    with engine.connect() as conn:
        return conn.execute(sa.select(orders_table.c.status).where(orders_table.c.id == order_id)).scalar_one()


def _pending_retry_job(engine, order_id) -> sa.RowMapping:
    with engine.connect() as conn:
        return (
            conn.execute(
                sa.select(background_jobs_table).where(
                    background_jobs_table.c.job_type == "submit_supplier_order",
                    background_jobs_table.c.payload["order_id"].astext == str(order_id),
                )
            )
            .mappings()
            .one()
        )


def test_submit_supplier_order_creates_supplier_order_and_attempt(engine, queue, order_id):
    client = _FakeAllianceTekClient()

    submit_supplier_order.handle({"order_id": str(order_id)}, engine, queue, client=client)

    with engine.connect() as conn:
        supplier_order = conn.execute(
            sa.select(supplier_orders_table).where(supplier_orders_table.c.order_id == order_id)
        ).mappings().one()
        attempts = list(
            conn.execute(
                sa.select(supplier_attempts_table).where(
                    supplier_attempts_table.c.supplier_order_id == supplier_order["id"]
                )
            ).mappings()
        )

    assert supplier_order["provider"] == "alliancetek"
    assert supplier_order["status"] == SupplierOrderStatus.SUPPLIER_ACCEPTED
    assert supplier_order["supplier_order_number"] == _public_order_number(engine, order_id)
    assert len(attempts) == 1
    assert attempts[0]["attempt_number"] == 1
    assert attempts[0]["status"] == "success"

    assert len(client.calls) == 1
    sent = client.calls[0]
    assert sent["orderNumber"] == _public_order_number(engine, order_id)
    assert sent["orderStatus"] == "awaiting_shipment"
    assert sent["items"] == [
        {"sku": "SUP-SKU-1", "name": "Supplier Test Product", "quantity": 1, "unitPrice": 19.99}
    ]


def test_submit_supplier_order_retry_reuses_same_supplier_order_number(engine, queue, order_id):
    client = _FakeAllianceTekClient()

    submit_supplier_order.handle({"order_id": str(order_id)}, engine, queue, client=client)
    submit_supplier_order.handle({"order_id": str(order_id)}, engine, queue, client=client)

    with engine.connect() as conn:
        supplier_orders = list(
            conn.execute(
                sa.select(supplier_orders_table).where(supplier_orders_table.c.order_id == order_id)
            ).mappings()
        )
        assert len(supplier_orders) == 1  # never a second row on retry
        attempts = list(
            conn.execute(
                sa.select(supplier_attempts_table).where(
                    supplier_attempts_table.c.supplier_order_id == supplier_orders[0]["id"]
                )
            ).mappings()
        )

    assert sorted(a["attempt_number"] for a in attempts) == [1, 2]
    # AllianceTek's confirmed idempotency rule: every retry sends the
    # exact same orderNumber, never a freshly generated one.
    assert client.calls[0]["orderNumber"] == client.calls[1]["orderNumber"]


def test_submit_supplier_order_reads_only_snapshot_fields_not_live_variant(engine, queue, order_id):
    """Renaming the live product_variants row after the order was placed
    must never change what gets submitted — payload building reads only
    order_items.*_at_purchase (see worker/alliancetek/payload.py)."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE product_variants SET name = 'Renamed Live Variant' "
                "WHERE id = (SELECT product_variant_id FROM order_items WHERE order_id = :order_id LIMIT 1)"
            ),
            {"order_id": order_id},
        )

    client = _FakeAllianceTekClient()
    submit_supplier_order.handle({"order_id": str(order_id)}, engine, queue, client=client)

    sent_item = client.calls[0]["items"][0]
    assert sent_item["name"] == "Supplier Test Product"
    assert sent_item["name"] != "Renamed Live Variant"


# ---------------------------------------------------------------------------
# Retry classification and bounded backoff.
# ---------------------------------------------------------------------------


def test_transient_failure_schedules_delayed_retry_not_generic_requeue(engine, queue, order_id):
    client = _FakeAllianceTekClient(errors=[_supplier_api_error(status_code=503)])

    submit_supplier_order.handle({"order_id": str(order_id)}, engine, queue, client=client)

    # The order/supplier_order are unaffected by a transient failure —
    # no MANUAL_REVIEW, no order_events row.
    assert _order_status(engine, order_id) == OrderStatus.PAYMENT_PENDING
    with engine.connect() as conn:
        supplier_order = conn.execute(
            sa.select(supplier_orders_table).where(supplier_orders_table.c.order_id == order_id)
        ).mappings().one()
    assert supplier_order["status"] == SupplierOrderStatus.PENDING

    retry_job = _pending_retry_job(engine, order_id)
    assert retry_job["payload"]["supplier_retry_count"] == 1
    # First retry tier is "immediate" (0s) — available_at should be at or
    # very close to now, not far in the future.
    seconds_until_available = (retry_job["available_at"] - datetime.now(timezone.utc)).total_seconds()
    assert seconds_until_available < 5

    with engine.connect() as conn:
        attempts = list(
            conn.execute(
                sa.select(supplier_attempts_table).where(
                    supplier_attempts_table.c.supplier_order_id == supplier_order["id"]
                )
            ).mappings()
        )
    assert len(attempts) == 1
    assert attempts[0]["status"] == "failed"


def test_permanent_failure_on_first_attempt_goes_straight_to_manual_review(engine, queue, order_id):
    client = _FakeAllianceTekClient(errors=[_supplier_api_error(status_code=401)])  # auth error

    submit_supplier_order.handle({"order_id": str(order_id)}, engine, queue, client=client)

    assert len(client.calls) == 1  # zero retries attempted
    assert _order_status(engine, order_id) == OrderStatus.MANUAL_REVIEW

    with engine.connect() as conn:
        supplier_order = conn.execute(
            sa.select(supplier_orders_table).where(supplier_orders_table.c.order_id == order_id)
        ).mappings().one()
        events = list(
            conn.execute(
                sa.select(order_events_table).where(order_events_table.c.order_id == order_id)
            ).mappings()
        )
    assert supplier_order["status"] == SupplierOrderStatus.MANUAL_REVIEW
    assert len(events) == 1
    assert events[0]["event_type"] == "status_changed"
    assert events[0]["data"]["to"] == OrderStatus.MANUAL_REVIEW

    # No retry job was scheduled — this was permanent, not transient.
    with pytest.raises(sa.exc.NoResultFound):
        _pending_retry_job(engine, order_id)


def test_config_error_also_routes_to_manual_review(engine, queue, order_id):
    """A missing SUPPLIER_API_ORDERS_URL isn't a customer-data problem,
    but it still needs a human — same MANUAL_REVIEW destination as a bad
    SKU, distinguishable by the recorded error message."""
    client = _FakeAllianceTekClient(errors=[SupplierApiConfigError("SUPPLIER_API_ORDERS_URL is not configured.")])

    submit_supplier_order.handle({"order_id": str(order_id)}, engine, queue, client=client)

    assert _order_status(engine, order_id) == OrderStatus.MANUAL_REVIEW
    with engine.connect() as conn:
        attempts = list(
            conn.execute(
                sa.select(supplier_attempts_table.c.error_message).where(
                    supplier_attempts_table.c.supplier_order_id.in_(
                        sa.select(supplier_orders_table.c.id).where(supplier_orders_table.c.order_id == order_id)
                    )
                )
            )
        )
    assert "not configured" in attempts[0].error_message


def test_exhausting_all_retry_tiers_routes_to_manual_review(engine, queue, order_id):
    """Simulates every retry tier failing transiently in a row — each
    failure re-enqueues the next attempt, and after RETRY_DELAYS_SECONDS
    is exhausted (5 retries beyond the original attempt, 6 total), the
    order is routed to MANUAL_REVIEW instead of retrying forever."""
    total_attempts = len(RETRY_DELAYS_SECONDS) + 1
    client = _FakeAllianceTekClient(errors=[_supplier_api_error(status_code=500) for _ in range(total_attempts)])

    current_payload = {"order_id": str(order_id)}
    for _ in range(total_attempts):
        submit_supplier_order.handle(current_payload, engine, queue, client=client)
        status = _order_status(engine, order_id)
        if status == OrderStatus.MANUAL_REVIEW:
            break
        retry_job = _pending_retry_job(engine, order_id)
        current_payload = dict(retry_job["payload"])
        with engine.begin() as conn:
            conn.execute(sa.delete(background_jobs_table).where(background_jobs_table.c.id == retry_job["id"]))

    assert len(client.calls) == total_attempts
    assert _order_status(engine, order_id) == OrderStatus.MANUAL_REVIEW
    with engine.connect() as conn:
        supplier_order = conn.execute(
            sa.select(supplier_orders_table).where(supplier_orders_table.c.order_id == order_id)
        ).mappings().one()
        attempts = list(
            conn.execute(
                sa.select(supplier_attempts_table).where(
                    supplier_attempts_table.c.supplier_order_id == supplier_order["id"]
                )
            ).mappings()
        )
    assert len(attempts) == total_attempts
    assert all(a["status"] == "failed" for a in attempts)


def test_eventual_success_after_a_transient_retry(engine, queue, order_id):
    client = _FakeAllianceTekClient(errors=[_supplier_api_error(status_code=502)])

    submit_supplier_order.handle({"order_id": str(order_id)}, engine, queue, client=client)
    retry_job = _pending_retry_job(engine, order_id)
    submit_supplier_order.handle(dict(retry_job["payload"]), engine, queue, client=client)

    assert len(client.calls) == 2
    with engine.connect() as conn:
        supplier_order = conn.execute(
            sa.select(supplier_orders_table).where(supplier_orders_table.c.order_id == order_id)
        ).mappings().one()
        attempts = list(
            conn.execute(
                sa.select(supplier_attempts_table).where(
                    supplier_attempts_table.c.supplier_order_id == supplier_order["id"]
                )
            ).mappings()
        )
    assert supplier_order["status"] == SupplierOrderStatus.SUPPLIER_ACCEPTED
    assert sorted(a["attempt_number"] for a in attempts) == [1, 2]
    assert [a["status"] for a in sorted(attempts, key=lambda a: a["attempt_number"])] == ["failed", "success"]
