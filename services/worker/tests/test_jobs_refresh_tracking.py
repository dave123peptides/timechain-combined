from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy import create_engine, text

import pytest

from worker.config import get_settings
from worker.db import (
    order_items_table,
    orders_table,
    shipments_table,
    supplier_attempts_table,
    supplier_orders_table,
    tracking_events_table,
)
from worker.jobs import refresh_tracking
from worker.order_status import OrderStatus, SupplierOrderStatus
from worker.queue.local import LocalQueueProvider

_TEST_EMAIL = "test-worker-tracking@example.invalid"
_SHIPPING_ADDRESS = {
    "line1": "1 Test St",
    "line2": None,
    "city": "Testville",
    "region": "CA",
    "postal_code": "90210",
    "country": "US",
}


class _FakeAllianceTekClient:
    """Stub AllianceTek client — returns pre-canned fulfillments/shipments
    responses so a test can simulate "no tracking yet" vs "tracking has
    since appeared" without a real network call."""

    def __init__(self, *, fulfillments: object = None, shipments: object = None):
        self._fulfillments = fulfillments if fulfillments is not None else {"result": {}}
        self._shipments = shipments if shipments is not None else {"result": {}}
        self.calls: list[str] = []

    def list_fulfillments(self, order_number: str) -> object:
        self.calls.append(f"fulfillments:{order_number}")
        return self._fulfillments

    def list_shipments(self, order_number: str) -> object:
        self.calls.append(f"shipments:{order_number}")
        return self._shipments


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
    """Same minimal product/variant/order/order_item row set as
    test_jobs_submit_supplier_order.py's order_id fixture."""
    product_id = uuid.uuid4()
    variant_id = uuid.uuid4()
    order = uuid.uuid4()
    item_id = uuid.uuid4()
    public_order_number = f"TCP-TST{uuid.uuid4().hex[:6].upper()}"

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO products (id, slug, name) VALUES (:id, :slug, :name)"),
            {"id": product_id, "slug": f"test-worker-tracking-{product_id}", "name": "Test Product"},
        )
        conn.execute(
            text(
                "INSERT INTO product_variants (id, product_id, sku, name, retail_price_cents) "
                "VALUES (:id, :product_id, :sku, :name, :price)"
            ),
            {"id": variant_id, "product_id": product_id, "sku": f"TEST-{variant_id}", "name": "Test Variant", "price": 1999},
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
        conn.execute(
            sa.delete(tracking_events_table).where(
                tracking_events_table.c.shipment_id.in_(
                    sa.select(shipments_table.c.id).where(shipments_table.c.order_id == order)
                )
            )
        )
        conn.execute(sa.delete(shipments_table).where(shipments_table.c.order_id == order))
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


def _insert_supplier_order(engine, order_id, public_order_number: str) -> uuid.UUID:
    supplier_order_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            sa.insert(supplier_orders_table).values(
                id=supplier_order_id,
                order_id=order_id,
                supplier_order_number=public_order_number,
                provider="alliancetek",
                status=SupplierOrderStatus.SUPPLIER_ACCEPTED,
                currency="usd",
            )
        )
    return supplier_order_id


def _public_order_number(engine, order_id) -> str:
    with engine.connect() as conn:
        return conn.execute(
            sa.select(orders_table.c.public_order_number).where(orders_table.c.id == order_id)
        ).scalar_one()


def test_tracking_missing_before_supplier_order_exists_is_a_noop(engine, queue, order_id):
    """No supplier_order row yet (order hasn't been submitted to
    AllianceTek at all) — must skip cleanly, never raise, never write a
    shipment out of nothing."""
    client = _FakeAllianceTekClient()

    refresh_tracking.handle({"order_id": str(order_id)}, engine, queue, client=client)

    assert client.calls == []  # never even calls the supplier API
    with engine.connect() as conn:
        shipments = list(
            conn.execute(sa.select(shipments_table).where(shipments_table.c.order_id == order_id)).mappings()
        )
    assert shipments == []


def test_tracking_missing_after_submission_writes_nothing(engine, queue, order_id):
    """supplier_order exists (order was submitted) but AllianceTek has no
    fulfillment/shipment records yet — a real, common "no tracking yet"
    state, not an error."""
    public_order_number = _public_order_number(engine, order_id)
    _insert_supplier_order(engine, order_id, public_order_number)
    client = _FakeAllianceTekClient(fulfillments={"result": {}}, shipments={"result": {}})

    refresh_tracking.handle({"order_id": str(order_id)}, engine, queue, client=client)

    assert client.calls == [f"fulfillments:{public_order_number}", f"shipments:{public_order_number}"]
    with engine.connect() as conn:
        shipments = list(
            conn.execute(sa.select(shipments_table).where(shipments_table.c.order_id == order_id)).mappings()
        )
    assert shipments == []


def test_tracking_later_appearing_writes_shipment_and_event(engine, queue, order_id):
    """Simulates two polls of the same order: first with no tracking data
    (as above), then a later poll where AllianceTek has since attached a
    real shipment — the second call must pick it up."""
    public_order_number = _public_order_number(engine, order_id)
    _insert_supplier_order(engine, order_id, public_order_number)

    empty_client = _FakeAllianceTekClient(fulfillments={"result": {}}, shipments={"result": {}})
    refresh_tracking.handle({"order_id": str(order_id)}, engine, queue, client=empty_client)

    later_client = _FakeAllianceTekClient(
        shipments={
            "result": {
                "shipments": [
                    {
                        "trackingNumber": "1Z999AA10123456784",
                        "carrier": "UPS",
                        "status": "shipped",
                        "shipDate": "2026-08-14T10:00:00Z",
                        "description": "Departed facility",
                    }
                ]
            }
        }
    )
    refresh_tracking.handle({"order_id": str(order_id)}, engine, queue, client=later_client)

    with engine.connect() as conn:
        shipment = conn.execute(
            sa.select(shipments_table).where(shipments_table.c.order_id == order_id)
        ).mappings().one()
        events = list(
            conn.execute(
                sa.select(tracking_events_table).where(tracking_events_table.c.shipment_id == shipment["id"])
            ).mappings()
        )

    assert shipment["tracking_number"] == "1Z999AA10123456784"
    assert shipment["carrier"] == "UPS"
    assert shipment["status"] == "shipped"
    assert len(events) == 1
    assert events[0]["status"] == "shipped"
    assert events[0]["description"] == "Departed facility"


def test_refresh_tracking_is_idempotent_across_repeated_polls(engine, queue, order_id):
    """Polling again with the exact same shipment/status must not
    accumulate duplicate tracking_events rows — see refresh_tracking's
    own docstring on why (runs repeatedly for the same order)."""
    public_order_number = _public_order_number(engine, order_id)
    _insert_supplier_order(engine, order_id, public_order_number)

    shipment_response = {
        "result": {
            "shipments": [
                {
                    "trackingNumber": "1Z999AA10123456784",
                    "carrier": "UPS",
                    "status": "shipped",
                    "shipDate": "2026-08-14T10:00:00Z",
                }
            ]
        }
    }
    client = _FakeAllianceTekClient(shipments=shipment_response)

    refresh_tracking.handle({"order_id": str(order_id)}, engine, queue, client=client)
    refresh_tracking.handle({"order_id": str(order_id)}, engine, queue, client=client)

    with engine.connect() as conn:
        shipments = list(
            conn.execute(sa.select(shipments_table).where(shipments_table.c.order_id == order_id)).mappings()
        )
        events = list(
            conn.execute(
                sa.select(tracking_events_table).where(
                    tracking_events_table.c.shipment_id.in_(sa.select(shipments_table.c.id).where(shipments_table.c.order_id == order_id))
                )
            ).mappings()
        )

    assert len(shipments) == 1  # updated in place, not duplicated
    assert len(events) == 1  # no duplicate event for the same status/occurred_at
