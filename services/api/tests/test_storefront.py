from __future__ import annotations

import dataclasses
import itertools
import re

import pytest
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping
from app.models.orders import Order
from app.api.shop import order_response
from app.services import storefront

_TEST_SLUG_PREFIX = "test-storefront"
_TEST_EMAIL = "test-storefront@example.invalid"
_TEST_SUPPLIER_PRODUCT_ID_START = 999401
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
        # consent_records cascades from orders (ON DELETE CASCADE) — no
        # separate cleanup needed for it. payments is ON DELETE RESTRICT
        # though, so it must be deleted explicitly before orders.
        # background_jobs has no FK to orders at all (worker/api are
        # separate containers/tables — see app/services/queue.py), so it
        # never blocks the order delete, but still needs explicit cleanup.
        session.execute(
            text("DELETE FROM background_jobs WHERE (payload->>'order_id')::uuid = ANY(:ids)"), {"ids": order_ids}
        )
        session.execute(text("DELETE FROM payments WHERE order_id = ANY(:ids)"), {"ids": order_ids})
        session.execute(text("DELETE FROM order_events WHERE order_id = ANY(:ids)"), {"ids": order_ids})
        session.execute(text("DELETE FROM order_items WHERE order_id = ANY(:ids)"), {"ids": order_ids})
        session.execute(text("DELETE FROM orders WHERE id = ANY(:ids)"), {"ids": order_ids})
    session.execute(text("DELETE FROM products WHERE slug LIKE :prefix"), {"prefix": f"{_TEST_SLUG_PREFIX}%"})
    # Bounded range, not `>=`: real AllianceTek supplier_product_ids are
    # much larger 8-digit numbers (e.g. 26395382) than this test range —
    # an unbounded `>=` here would delete real supplier catalog data.
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


def _make_product(session, slug_suffix: str, *, description=None, category=None, images=None):
    product = Product(
        slug=f"{_TEST_SLUG_PREFIX}-{slug_suffix}",
        name=f"Test Product {slug_suffix}",
        description=description,
        category=category,
        images=images or [],
        is_active=False,
    )
    session.add(product)
    session.flush()
    return product


def _make_variant(
    session, product, suffix: str, *, price_cents: int, sellable: bool, form="vial", size_key="10",
    mapping_status: str = "MAPPED",
):
    variant = ProductVariant(
        product_id=product.id,
        sku=f"TC-TEST-STOREFRONT-{suffix.upper()}",
        name=f"{product.name} {size_key}mg",
        retail_price_cents=price_cents,
        form=form,
        size_key=size_key,
    )
    session.add(variant)
    session.flush()
    if sellable:
        # create_order re-checks get_mapping_status() explicitly (not
        # just is_sellable) — give sellable test variants a real
        # supplier mapping so that check has something genuine to find.
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
                mapping_status=mapping_status,
            )
        )
        session.flush()
        # Bypass ProductVariant._validate_is_sellable via raw SQL rather
        # than the ORM setter: this file tests how storefront.py reacts
        # to is_sellable/mapping status, not the validator itself (see
        # test_sellable_guard.py for that). Also lets a test construct
        # the "is_sellable=True but mapping isn't actually MAPPED"
        # scenario the validator would normally prevent — exactly what
        # the explicit re-check in create_order guards against.
        session.execute(text("UPDATE product_variants SET is_sellable = true WHERE id = :id"), {"id": variant.id})
        session.commit()
        session.refresh(variant)
    return variant


def test_format_label_recognizes_preconstituted():
    assert storefront._format_label("preconstituted") == "Preconstituted"
    assert storefront._format_label("lyophilized") == "Lyophilized"


def test_list_sellable_products_excludes_unsellable_variants(session):
    product = _make_product(session, "list-mixed")
    _make_variant(session, product, "sellable", price_cents=1000, sellable=True)
    _make_variant(session, product, "unsellable", price_cents=2000, sellable=False)

    other_product = _make_product(session, "list-none-sellable")
    _make_variant(session, other_product, "only-unsellable", price_cents=500, sellable=False)

    results = storefront.list_sellable_products(session)
    slugs = {row.slug for row in results}

    assert product.slug in slugs
    assert other_product.slug not in slugs

    row = next(r for r in results if r.slug == product.slug)
    assert row.starting_price_cents == 1000  # only the sellable variant counts


def test_storefront_dataclasses_have_no_supplier_fields():
    """Structural guard: even if the query logic changed, these response
    types are physically incapable of carrying supplier_sku/
    supplier_name/supplier_product_id — there's no field for it."""
    variant_fields = {f.name for f in dataclasses.fields(storefront.StorefrontVariant)}
    product_fields = {f.name for f in dataclasses.fields(storefront.StorefrontProductDetail)}
    forbidden = {"supplier_sku", "supplier_name", "supplier_product_id", "sku"}
    assert not (variant_fields & forbidden)
    assert not (product_fields & forbidden)


def test_get_sellable_product_by_slug_none_when_no_sellable_variants(session):
    product = _make_product(session, "detail-none-sellable")
    _make_variant(session, product, "unsellable", price_cents=1000, sellable=False)

    assert storefront.get_sellable_product_by_slug(session, product.slug) is None


def test_get_sellable_product_by_slug_none_when_product_does_not_exist(session):
    assert storefront.get_sellable_product_by_slug(session, "does-not-exist") is None


def test_get_sellable_product_by_slug_returns_only_sellable_variants(session):
    product = _make_product(session, "detail-mixed", description="A test compound.", category="Test Category")
    _make_variant(session, product, "a", price_cents=1000, sellable=True, size_key="10")
    _make_variant(session, product, "b", price_cents=2000, sellable=False, size_key="20")

    result = storefront.get_sellable_product_by_slug(session, product.slug)

    assert result is not None
    assert result.description == "A test compound."
    assert len(result.variants) == 1
    assert result.variants[0].price_cents == 1000


def test_create_order_computes_totals_server_side(session):
    product = _make_product(session, "order-ok")
    variant = _make_variant(session, product, "ok", price_cents=1500, sellable=True)

    order = storefront.create_order(
        session,
        email=_TEST_EMAIL,
        shipping_address=_SHIPPING_ADDRESS,
        items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=3)],
        consent=_VALID_CONSENT,
        payment_method="crypto",
    )

    assert order.subtotal_cents == 4500
    assert order.shipping_cents == 4000
    assert order.tax_cents == 0
    assert order.total_cents == 8500
    assert order.status == "PAYMENT_PENDING"
    assert order.access_token
    assert re.match(r"^PEN-[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}$", order.public_order_number)
    assert len(order.items) == 1
    assert order.items[0].unit_price_cents == 1500
    assert order.items[0].sku_snapshot == variant.sku


def test_create_order_rejects_unsellable_variant_and_writes_nothing(session):
    product = _make_product(session, "order-reject")
    variant = _make_variant(session, product, "reject", price_cents=1000, sellable=False)

    with pytest.raises(storefront.StorefrontError, match="no longer available"):
        storefront.create_order(
            session,
            email=_TEST_EMAIL,
            shipping_address=_SHIPPING_ADDRESS,
            items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)],
            consent=_VALID_CONSENT,
            payment_method="crypto",
        )

    remaining = session.execute(select(Order).where(Order.customer_email == _TEST_EMAIL)).scalars().all()
    assert remaining == []


def test_create_order_rejects_empty_cart(session):
    with pytest.raises(storefront.StorefrontError, match="empty"):
        storefront.create_order(
            session, email=_TEST_EMAIL, shipping_address=_SHIPPING_ADDRESS, items=[], consent=_VALID_CONSENT,
            payment_method="crypto",
        )


def test_create_order_price_always_comes_from_the_database():
    """OrderItemRequest structurally has no price field at all — a client
    can't submit one even if it tried. This documents that guarantee
    rather than testing a bypass that isn't reachable."""
    request_fields = {f.name for f in dataclasses.fields(storefront.OrderItemRequest)}
    assert "price_cents" not in request_fields
    assert "unit_price_cents" not in request_fields


def test_get_order_by_token_roundtrip_and_unknown_token(session):
    product = _make_product(session, "order-token")
    variant = _make_variant(session, product, "token", price_cents=1000, sellable=True)
    order = storefront.create_order(
        session,
        email=_TEST_EMAIL,
        shipping_address=_SHIPPING_ADDRESS,
        items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)],
        consent=_VALID_CONSENT,
        payment_method="crypto",
    )

    found = storefront.get_order_by_token(session, order.access_token)
    assert found is not None
    assert found.id == order.id

    assert storefront.get_order_by_token(session, "not-a-real-token") is None


# ---------------------------------------------------------------------------
# Consent — checkout must require all three acknowledgments and persist a
# ConsentRecord; nothing is written if any is missing.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "consent,match",
    [
        (storefront.ConsentInput(age_confirmed=False, ruo_acknowledged=True, terms_accepted=True), "21 years old"),
        (storefront.ConsentInput(age_confirmed=True, ruo_acknowledged=False, terms_accepted=True), "Research Use Only"),
        (storefront.ConsentInput(age_confirmed=True, ruo_acknowledged=True, terms_accepted=False), "Terms of Service"),
    ],
)
def test_create_order_rejects_missing_consent_and_writes_nothing(session, consent, match):
    product = _make_product(session, "order-no-consent")
    variant = _make_variant(session, product, "no-consent", price_cents=1000, sellable=True)

    with pytest.raises(storefront.StorefrontError, match=match):
        storefront.create_order(
            session,
            email=_TEST_EMAIL,
            shipping_address=_SHIPPING_ADDRESS,
            items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)],
            consent=consent,
            payment_method="crypto",
        )

    remaining = session.execute(select(Order).where(Order.customer_email == _TEST_EMAIL)).scalars().all()
    assert remaining == []


def test_create_order_persists_consent_record_with_version_stamps(session):
    product = _make_product(session, "order-consent-ok")
    variant = _make_variant(session, product, "consent-ok", price_cents=1000, sellable=True)

    order = storefront.create_order(
        session,
        email=_TEST_EMAIL,
        shipping_address=_SHIPPING_ADDRESS,
        items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)],
        consent=_VALID_CONSENT,
        payment_method="crypto",
    )

    consent_row = session.execute(
        text("SELECT age_acknowledged_at, ruo_acknowledged_at, ruo_terms_version, terms_version, privacy_version "
             "FROM consent_records WHERE order_id = :order_id"),
        {"order_id": order.id},
    ).one()
    assert consent_row.age_acknowledged_at is not None
    assert consent_row.ruo_acknowledged_at is not None
    assert consent_row.ruo_terms_version == storefront.RUO_TERMS_VERSION
    assert consent_row.terms_version == storefront.TERMS_VERSION
    assert consent_row.privacy_version == storefront.PRIVACY_VERSION


# ---------------------------------------------------------------------------
# Shipping — US-only flat rate sourced from system_settings.
# ---------------------------------------------------------------------------


def test_create_order_rejects_non_us_shipping_address(session):
    product = _make_product(session, "order-non-us")
    variant = _make_variant(session, product, "non-us", price_cents=1000, sellable=True)
    non_us_address = {**_SHIPPING_ADDRESS, "country": "CA"}

    with pytest.raises(storefront.StorefrontError, match="United States only"):
        storefront.create_order(
            session,
            email=_TEST_EMAIL,
            shipping_address=non_us_address,
            items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)],
            consent=_VALID_CONSENT,
            payment_method="crypto",
        )

    remaining = session.execute(select(Order).where(Order.customer_email == _TEST_EMAIL)).scalars().all()
    assert remaining == []


def test_build_quote_is_read_only_and_matches_create_order_math(session):
    """POST /api/v1/checkout/quote's implementation. Read-only — asserts
    nothing was written — and must agree exactly with what create_order
    would actually charge, since both share the same pricing/shipping/
    tax functions."""
    product = _make_product(session, "quote-ok")
    variant = _make_variant(session, product, "quote-ok", price_cents=3000, sellable=True)

    quote = storefront.build_quote(
        session, items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=2)]
    )

    assert quote.subtotal_cents == 6000
    assert quote.shipping_cents == 4000
    assert quote.tax_cents == 0
    assert quote.total_cents == 10000
    assert len(quote.items) == 1
    assert quote.items[0].name == variant.name
    assert quote.items[0].total_price_cents == 6000

    remaining = session.execute(select(Order).where(Order.customer_email == _TEST_EMAIL)).scalars().all()
    assert remaining == []


def test_build_quote_rejects_unsellable_variant(session):
    product = _make_product(session, "quote-reject")
    variant = _make_variant(session, product, "quote-reject", price_cents=1000, sellable=False)

    with pytest.raises(storefront.StorefrontError, match="no longer available"):
        storefront.build_quote(session, items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)])


def test_build_quote_rejects_non_us_country(session):
    product = _make_product(session, "quote-non-us")
    variant = _make_variant(session, product, "quote-non-us", price_cents=1000, sellable=True)

    with pytest.raises(storefront.StorefrontError, match="United States only"):
        storefront.build_quote(
            session, items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)], country="CA"
        )


def test_checkout_item_request_has_no_price_field():
    """Same structural guarantee as OrderItemRequest — the quote endpoint
    takes variant_id/quantity only, never a price, from the frontend."""
    request_fields = {f.name for f in dataclasses.fields(storefront.OrderItemRequest)}
    assert "price_cents" not in request_fields


def test_calculate_tax_cents_is_a_real_computed_step(session):
    """Documents today's placeholder behavior (always 0) without baking
    that assumption into callers — see the function's own docstring:
    "callers must not assume this stays 0". This test should be revisited
    the day a real tax engine replaces the body."""
    assert storefront.calculate_tax_cents(session, subtotal_cents=10000, shipping_address=_SHIPPING_ADDRESS) == 0


def test_create_order_creates_a_pending_payment_checkout(session):
    product = _make_product(session, "order-payment")
    variant = _make_variant(session, product, "payment", price_cents=1000, sellable=True)

    order = storefront.create_order(
        session,
        email=_TEST_EMAIL,
        shipping_address=_SHIPPING_ADDRESS,
        items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)],
        consent=_VALID_CONSENT,
        payment_method="crypto",
    )

    payment_row = session.execute(
        text("SELECT provider, status, amount_cents, currency FROM payments WHERE order_id = :order_id"),
        {"order_id": order.id},
    ).one()
    assert payment_row.status == "pending"
    assert payment_row.amount_cents == order.total_cents
    assert payment_row.currency == "usd"
    # Records what the customer selected at checkout — not a fabricated
    # success. Stays "pending" until app.services.payments.mark_order_paid
    # confirms it actually cleared.
    assert payment_row.provider == "crypto"


def test_get_shipping_quote_reads_the_seeded_system_setting(session):
    quote = storefront.get_shipping_quote(session)
    assert quote.country == "US"
    assert quote.amount_cents == 4000  # matches the migration-seeded system_settings row


def test_create_order_totals_include_shipping_from_system_settings(session):
    product = _make_product(session, "order-shipping-total")
    variant = _make_variant(session, product, "shipping-total", price_cents=2500, sellable=True)

    order = storefront.create_order(
        session,
        email=_TEST_EMAIL,
        shipping_address=_SHIPPING_ADDRESS,
        items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)],
        consent=_VALID_CONSENT,
        payment_method="crypto",
    )

    assert order.subtotal_cents == 2500
    assert order.shipping_cents == 4000
    assert order.total_cents == 6500


# ---------------------------------------------------------------------------
# Cart integrity — explicit supplier-mapping re-check at checkout, not just
# is_sellable.
# ---------------------------------------------------------------------------


def test_create_order_rejects_variant_whose_mapping_is_not_actually_mapped(session):
    """Constructs the scenario ProductVariant._validate_is_sellable
    normally prevents (is_sellable=True with no verified mapping) via the
    raw-SQL bypass in _make_variant, proving create_order's explicit
    get_mapping_status() re-check catches it independently — cart
    integrity at checkout doesn't just trust the is_sellable column."""
    product = _make_product(session, "order-bad-mapping")
    variant = _make_variant(
        session, product, "bad-mapping", price_cents=1000, sellable=True, mapping_status="CHANGED"
    )

    with pytest.raises(storefront.StorefrontError, match="no longer available"):
        storefront.create_order(
            session,
            email=_TEST_EMAIL,
            shipping_address=_SHIPPING_ADDRESS,
            items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)],
            consent=_VALID_CONSENT,
            payment_method="crypto",
        )

    remaining = session.execute(select(Order).where(Order.customer_email == _TEST_EMAIL)).scalars().all()
    assert remaining == []


# ---------------------------------------------------------------------------
# OrderItem snapshots — supplier identity frozen at purchase time, and the
# submit_supplier_order job enqueued in the same transaction as the order.
# ---------------------------------------------------------------------------


def test_create_order_persists_supplier_snapshot_fields(session):
    product = _make_product(session, "order-snapshot")
    variant = _make_variant(session, product, "snapshot", price_cents=2000, sellable=True)
    variant.wholesale_cost_cents = 750
    session.flush()

    mapping = session.execute(
        select(SupplierProductMapping).where(SupplierProductMapping.product_variant_id == variant.id)
    ).scalar_one()

    order = storefront.create_order(
        session,
        email=_TEST_EMAIL,
        shipping_address=_SHIPPING_ADDRESS,
        items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=2)],
        consent=_VALID_CONSENT,
        payment_method="crypto",
    )

    item = order.items[0]
    assert item.display_name_at_purchase == variant.name
    assert item.supplier_product_id_at_purchase == mapping.supplier_product_id
    assert item.supplier_sku_at_purchase == mapping.supplier_sku
    assert item.supplier_name_at_purchase == mapping.supplier_name
    assert item.wholesale_cost_cents == 750
    assert item.unit_price_cents == 2000


def test_historical_order_item_survives_later_catalog_and_mapping_changes(session):
    """The core guarantee: once an order exists, changing the live
    catalog/mapping data it was built from must never change what the
    order already recorded."""
    product = _make_product(session, "order-immutable")
    variant = _make_variant(session, product, "immutable", price_cents=1200, sellable=True)

    order = storefront.create_order(
        session,
        email=_TEST_EMAIL,
        shipping_address=_SHIPPING_ADDRESS,
        items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)],
        consent=_VALID_CONSENT,
        payment_method="crypto",
    )
    item_id = order.items[0].id
    original_supplier_sku = order.items[0].supplier_sku_at_purchase
    original_supplier_name = order.items[0].supplier_name_at_purchase
    original_display_name = order.items[0].display_name_at_purchase

    # Mutate the live mapping and variant name after the order exists —
    # a real re-sync/remap/rename, not a contrived edge case.
    mapping = session.execute(
        select(SupplierProductMapping).where(SupplierProductMapping.product_variant_id == variant.id)
    ).scalar_one()
    mapping.supplier_sku = "CHANGED-SKU"
    mapping.supplier_name = "Changed Supplier Name"
    variant.name = "Renamed Product"
    session.flush()
    session.commit()

    reloaded = session.execute(text("SELECT * FROM order_items WHERE id = :id"), {"id": item_id}).mappings().one()
    assert reloaded["supplier_sku_at_purchase"] == original_supplier_sku
    assert reloaded["supplier_name_at_purchase"] == original_supplier_name
    assert reloaded["display_name_at_purchase"] == original_display_name
    assert reloaded["supplier_sku_at_purchase"] != "CHANGED-SKU"
    assert reloaded["display_name_at_purchase"] != "Renamed Product"


def test_create_order_does_not_enqueue_fulfillment_before_payment(session):
    """Fulfillment must never start before payment clears — see
    create_order's docstring and app.services.payments.mark_order_paid,
    which is what enqueues submit_supplier_order now. This is a
    regression guard for a real bug: this job used to be enqueued
    unconditionally at order creation, before any payment existed."""
    product = _make_product(session, "order-enqueue")
    variant = _make_variant(session, product, "enqueue", price_cents=1000, sellable=True)

    order = storefront.create_order(
        session,
        email=_TEST_EMAIL,
        shipping_address=_SHIPPING_ADDRESS,
        items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)],
        consent=_VALID_CONSENT,
        payment_method="crypto",
    )
    session.commit()

    jobs = session.execute(
        text("SELECT job_type, payload FROM background_jobs WHERE (payload->>'order_id')::uuid = :order_id"),
        {"order_id": order.id},
    ).all()
    assert jobs == []


@pytest.mark.parametrize("method", ["venmo", "zelle"])
def test_create_order_records_manual_payment_method_and_exposes_it(session, method):
    """Venmo and Zelle (the launch methods, David 9/4) have no provider:
    the order is created PAYMENT_PENDING with a pending Payment row
    naming the method, no hosted-checkout instructions are attached, and
    the customer-facing response says which method was chosen so the
    order page can show the matching transfer instructions."""
    product = _make_product(session, f"order-{method}")
    variant = _make_variant(session, product, method, price_cents=1500, sellable=True)

    order = storefront.create_order(
        session,
        email=_TEST_EMAIL,
        shipping_address=_SHIPPING_ADDRESS,
        items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=1)],
        consent=_VALID_CONSENT,
        payment_method=method,
    )
    session.flush()

    assert order.status == "PAYMENT_PENDING"
    assert [payment.provider for payment in order.payments] == [method]
    assert [payment.status for payment in order.payments] == ["pending"]
    assert not hasattr(order, "payment_instructions")

    response = order_response(order)
    assert response.payment_method == method
    assert response.payment is None


def test_create_order_stores_customer_name_and_phone_and_exports_them(session, monkeypatch):
    """Manual fulfillment (David, 9/4): the order carries the full
    customer record, the CSV/webhook row is built from it, and the
    notification is a silent no-op while no webhook URL is configured."""
    from app.core.config import get_settings
    from app.services import order_notify
    from app.services.order_export import EXPORT_COLUMNS, list_export_rows, order_notification_payload, rows_to_csv

    product = _make_product(session, "order-customer")
    variant = _make_variant(session, product, "customer", price_cents=2500, sellable=True)
    order = storefront.create_order(
        session,
        email=_TEST_EMAIL,
        shipping_address=_SHIPPING_ADDRESS,
        items=[storefront.OrderItemRequest(variant_id=variant.id, quantity=2)],
        consent=_VALID_CONSENT,
        payment_method="venmo",
        customer_name="Test Customer",
        customer_phone="+1 305 555 0100",
    )
    session.flush()

    assert order.customer_name == "Test Customer"
    assert order.customer_phone == "+1 305 555 0100"
    response = order_response(order)
    assert (response.customer_name, response.customer_phone) == ("Test Customer", "+1 305 555 0100")

    row = next(r for r in list_export_rows(session) if r["order_number"] == order.public_order_number)
    assert row["customer_name"] == "Test Customer"
    assert row["payment_method"] == "venmo"
    assert row["item_count"] == 2
    assert "[supplier: " in row["items"]
    assert row["total"] == f"{order.total_cents / 100:.2f}"
    csv_text = rows_to_csv([row])
    assert csv_text.splitlines()[0] == ",".join(EXPORT_COLUMNS)
    assert order.public_order_number in csv_text

    payload = order_notification_payload(order, order_url="https://example.invalid/order/x")
    assert payload["order_url"] == "https://example.invalid/order/x"
    assert payload["items_detail"][0]["quantity"] == 2

    monkeypatch.setattr(get_settings(), "order_notify_webhook_url", "")
    assert order_notify.notify_new_order(payload) is False
