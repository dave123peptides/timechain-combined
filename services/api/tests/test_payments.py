from __future__ import annotations

import itertools

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping
from app.services import payments, storefront

_TEST_SLUG_PREFIX = "test-payments"
_TEST_EMAIL = "test-payments@example.invalid"
_TEST_SUPPLIER_PRODUCT_ID_START = 999501
_supplier_product_id_counter = itertools.count(_TEST_SUPPLIER_PRODUCT_ID_START)

_SHIPPING_ADDRESS = {
    "line1": "1 Test St",
    "line2": None,
    "city": "Testville",
    "region": "CA",
    "postal_code": "90210",
    "country": "US",
}

_VALID_CONSENT = storefront.ConsentInput(age_confirmed=True, ruo_acknowledged=True, terms_accepted=True)


def _cleanup(session):
    order_ids = [
        row[0]
        for row in session.execute(text("SELECT id FROM orders WHERE customer_email = :email"), {"email": _TEST_EMAIL})
    ]
    if order_ids:
        session.execute(
            text("DELETE FROM background_jobs WHERE (payload->>'order_id')::uuid = ANY(:ids)"), {"ids": order_ids}
        )
        session.execute(text("DELETE FROM payment_events WHERE payment_id IN (SELECT id FROM payments WHERE order_id = ANY(:ids))"), {"ids": order_ids})
        session.execute(text("DELETE FROM payments WHERE order_id = ANY(:ids)"), {"ids": order_ids})
        session.execute(text("DELETE FROM order_events WHERE order_id = ANY(:ids)"), {"ids": order_ids})
        session.execute(text("DELETE FROM order_items WHERE order_id = ANY(:ids)"), {"ids": order_ids})
        session.execute(text("DELETE FROM orders WHERE id = ANY(:ids)"), {"ids": order_ids})
    session.execute(text("DELETE FROM products WHERE slug LIKE :prefix"), {"prefix": f"{_TEST_SLUG_PREFIX}%"})
    session.execute(
        text("DELETE FROM supplier_products WHERE supplier_product_id BETWEEN :start AND :end"),
        {"start": _TEST_SUPPLIER_PRODUCT_ID_START, "end": _TEST_SUPPLIER_PRODUCT_ID_START + 9999},
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


def _make_paid_order(session, slug_suffix: str):
    """A fresh PAYMENT_PENDING order with one sellable variant — the
    starting state every mark_order_paid/mark_order_payment_failed test
    begins from."""
    product = Product(
        slug=f"{_TEST_SLUG_PREFIX}-{slug_suffix}", name=f"Test Product {slug_suffix}", images=[], is_active=False
    )
    session.add(product)
    session.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku=f"TC-TEST-PAYMENTS-{slug_suffix.upper()}",
        name=f"{product.name} 10mg",
        retail_price_cents=1000,
        form="vial",
        size_key="10",
    )
    session.add(variant)
    session.flush()

    supplier_product_id = next(_supplier_product_id_counter)
    supplier_product = SupplierProduct(
        supplier_product_id=supplier_product_id,
        supplier_sku=f"TEST-{supplier_product_id}",
        supplier_name=f"Test Supplier Product {supplier_product_id}",
        supplier_active=True,
        raw_payload={"productId": supplier_product_id},
    )
    session.add(supplier_product)
    session.flush()
    session.add(
        SupplierProductMapping(
            product_variant_id=variant.id,
            supplier_product_id=supplier_product_id,
            supplier_sku=supplier_product.supplier_sku,
            supplier_name=supplier_product.supplier_name,
            mapping_status="MAPPED",
        )
    )
    session.flush()
    session.execute(text("UPDATE product_variants SET is_sellable = true WHERE id = :id"), {"id": variant.id})
    session.commit()
    session.refresh(variant)

    order = storefront.create_order(
        session,
        email=_TEST_EMAIL,
        shipping_address=_SHIPPING_ADDRESS,
        items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)],
        consent=_VALID_CONSENT,
        payment_method="crypto",
    )
    session.commit()
    return order


def _jobs_for(session, order_id):
    return session.execute(
        text("SELECT job_type FROM background_jobs WHERE (payload->>'order_id')::uuid = :order_id"),
        {"order_id": order_id},
    ).all()


def test_mark_order_paid_transitions_status_and_enqueues_fulfillment(session, monkeypatch):
    """supplier_api mode — the original flow. (The default is now
    "manual", see test_mark_order_paid_manual_mode_records_event_instead.)"""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "fulfillment_mode", "supplier_api")
    order = _make_paid_order(session, "paid-ok")
    assert _jobs_for(session, order.id) == []

    payments.mark_order_paid(
        session, order_id=order.id, provider="crypto", provider_payment_id="tx123", source="admin:test"
    )
    session.commit()

    updated = session.execute(text("SELECT status FROM orders WHERE id = :id"), {"id": order.id}).one()
    assert updated.status == "PAID"

    jobs = _jobs_for(session, order.id)
    assert len(jobs) == 1
    assert jobs[0].job_type == "submit_supplier_order"

    payment_row = session.execute(
        text("SELECT status, provider, provider_payment_id FROM payments WHERE order_id = :id"), {"id": order.id}
    ).one()
    assert payment_row.status == "succeeded"
    assert payment_row.provider == "crypto"
    assert payment_row.provider_payment_id == "tx123"

    event_count = session.execute(
        text(
            "SELECT count(*) FROM payment_events pe JOIN payments p ON p.id = pe.payment_id "
            "WHERE p.order_id = :id AND pe.event_type = 'payment.confirmed'"
        ),
        {"id": order.id},
    ).scalar_one()
    assert event_count == 1


def test_mark_order_paid_is_idempotent(session, monkeypatch):
    """A retried webhook delivery (or an admin double-click) must never
    double-enqueue fulfillment or double-write payment history."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "fulfillment_mode", "supplier_api")
    order = _make_paid_order(session, "paid-idempotent")

    payments.mark_order_paid(session, order_id=order.id, provider="crypto", provider_payment_id="tx1", source="admin:test")
    session.commit()

    with pytest.raises(payments.PaymentActionError, match="not PAYMENT_PENDING"):
        payments.mark_order_paid(session, order_id=order.id, provider="crypto", provider_payment_id="tx2", source="admin:test")

    jobs = _jobs_for(session, order.id)
    assert len(jobs) == 1  # still exactly one — the second call wrote nothing


def test_mark_order_payment_failed_transitions_status_without_enqueueing(session):
    order = _make_paid_order(session, "failed-ok")

    payments.mark_order_payment_failed(session, order_id=order.id, source="admin:test", reason="never received")
    session.commit()

    updated = session.execute(text("SELECT status FROM orders WHERE id = :id"), {"id": order.id}).one()
    assert updated.status == "PAYMENT_FAILED"
    assert _jobs_for(session, order.id) == []

    payment_row = session.execute(text("SELECT status FROM payments WHERE order_id = :id"), {"id": order.id}).one()
    assert payment_row.status == "failed"


def test_mark_order_payment_failed_is_idempotent(session):
    order = _make_paid_order(session, "failed-idempotent")
    payments.mark_order_payment_failed(session, order_id=order.id, source="admin:test", reason="first")
    session.commit()

    with pytest.raises(payments.PaymentActionError, match="not PAYMENT_PENDING"):
        payments.mark_order_payment_failed(session, order_id=order.id, source="admin:test", reason="second")


def test_mark_order_paid_manual_mode_records_event_instead_of_enqueueing(session):
    """The launch default (David, 9/4): a paid order is placed with the
    supplier by a person, so nothing is enqueued — an
    awaiting_manual_fulfillment event is the hand-off record."""
    from app.core.config import get_settings

    assert get_settings().fulfillment_mode == "manual"
    order = _make_paid_order(session, "manual-mode")

    payments.mark_order_paid(session, order_id=order.id, provider="zelle", provider_payment_id=None, source="admin:test")
    session.commit()

    updated = session.execute(text("SELECT status FROM orders WHERE id = :id"), {"id": order.id}).one()
    assert updated.status == "PAID"
    assert _jobs_for(session, order.id) == []
    kinds = [
        row.event_type
        for row in session.execute(text("SELECT event_type FROM order_events WHERE order_id = :id"), {"id": order.id})
    ]
    assert "awaiting_manual_fulfillment" in kinds
