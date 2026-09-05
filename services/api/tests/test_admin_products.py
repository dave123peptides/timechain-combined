from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping
from app.models.events import AuditEvent
from app.services import admin_products

_TEST_SUPPLIER_PRODUCT_IDS = [999301, 999302, 999303]
_TEST_SLUG_PREFIX = "test-admin-products"


def _cleanup(session):
    variant_ids = [
        row[0]
        for row in session.execute(
            text(
                "SELECT pv.id FROM product_variants pv JOIN products p ON p.id = pv.product_id "
                "WHERE p.slug LIKE :prefix"
            ),
            {"prefix": f"{_TEST_SLUG_PREFIX}%"},
        )
    ]
    if variant_ids:
        session.execute(text("DELETE FROM audit_events WHERE entity_id = ANY(:ids)"), {"ids": variant_ids})
    session.execute(text("DELETE FROM products WHERE slug LIKE :prefix"), {"prefix": f"{_TEST_SLUG_PREFIX}%"})
    session.execute(
        text("DELETE FROM supplier_products WHERE supplier_product_id = ANY(:ids)"),
        {"ids": _TEST_SUPPLIER_PRODUCT_IDS},
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


def _make_supplier_product(session, supplier_product_id: int, *, sku: str, name: str, active: bool = True):
    supplier_product = SupplierProduct(
        supplier_product_id=supplier_product_id,
        supplier_sku=sku,
        supplier_name=name,
        supplier_active=active,
        supplier_key="nxgen",
        raw_payload={"productId": supplier_product_id, "sku": sku, "name": name},
    )
    session.add(supplier_product)
    session.flush()
    return supplier_product


def _make_variant(session, slug_suffix: str, *, name: str = "Test Widget 10mg pen", form: str = "pen"):
    product = Product(slug=f"{_TEST_SLUG_PREFIX}-{slug_suffix}", name="Test Widget", images=[], is_active=False)
    session.add(product)
    session.flush()
    variant = ProductVariant(
        product_id=product.id,
        sku=f"TC-TEST-ADMIN-{slug_suffix.upper()}",
        name=name,
        retail_price_cents=1000,
        wholesale_cost_cents=500,
        size_key="10",
        form=form,
    )
    session.add(variant)
    session.flush()
    return variant


def _make_mapping(session, variant, supplier_product, *, mapping_status: str = "MAPPED", match_confidence: str = "EXACT"):
    mapping = SupplierProductMapping(
        product_variant_id=variant.id,
        supplier_product_id=supplier_product.supplier_product_id,
        supplier_sku=supplier_product.supplier_sku,
        supplier_name=supplier_product.supplier_name,
        mapping_status=mapping_status,
        match_confidence=match_confidence,
    )
    session.add(mapping)
    session.flush()
    return mapping


def _audit_rows_for(session, variant_id):
    return list(
        session.execute(select(AuditEvent).where(AuditEvent.entity_id == variant_id).order_by(AuditEvent.created_at)).scalars()
    )


def test_enable_fails_without_mapped_and_writes_no_audit_event(session):
    variant = _make_variant(session, "enable-fail")

    with pytest.raises(admin_products.AdminActionError, match="MISSING"):
        admin_products.enable(session, variant_id=variant.id, actor="alice")

    assert variant.is_sellable is False
    assert _audit_rows_for(session, variant.id) == []


def test_enable_succeeds_when_mapped_and_writes_audit_event(session):
    supplier_product = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-1", name="Widget 1")
    variant = _make_variant(session, "enable-ok")
    _make_mapping(session, variant, supplier_product)

    admin_products.enable(session, variant_id=variant.id, actor="alice")

    assert variant.is_sellable is True
    audit = _audit_rows_for(session, variant.id)
    assert len(audit) == 1
    assert audit[0].actor == "alice"
    assert audit[0].action == "variant.enabled"


def test_disable_writes_audit_event(session):
    supplier_product = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-1", name="Widget 1")
    variant = _make_variant(session, "disable")
    _make_mapping(session, variant, supplier_product)
    admin_products.enable(session, variant_id=variant.id, actor="alice")

    admin_products.disable(session, variant_id=variant.id, actor="bob")

    assert variant.is_sellable is False
    audit = _audit_rows_for(session, variant.id)
    assert [event.action for event in audit] == ["variant.enabled", "variant.disabled"]
    assert audit[-1].actor == "bob"


def test_set_mapping_approve_creates_mapping_and_writes_audit_event(session):
    supplier_product = _make_supplier_product(
        session, _TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-1", name="Test Widget 10mg (Vial)"
    )
    variant = _make_variant(session, "approve", name="Test Widget 10mg (Vial)")

    mapping = admin_products.set_mapping(
        session,
        variant_id=variant.id,
        supplier_product_id=supplier_product.supplier_product_id,
        actor="alice",
        action_label="mapping.approved",
    )

    assert mapping.mapping_status == "MAPPED"
    assert mapping.supplier_sku == "SKU-1"
    audit = _audit_rows_for(session, variant.id)
    assert len(audit) == 1
    assert audit[0].action == "mapping.approved"
    assert audit[0].data["previous_supplier_product_id"] is None
    assert audit[0].data["new_supplier_product_id"] == supplier_product.supplier_product_id


def test_set_mapping_marks_manual_when_admin_overrides_the_top_candidate(session):
    """Regression guard: confidence must be computed against every
    supplier product, not just the chosen one — a single-candidate list
    would trivially make it "best" by default regardless of match
    quality, silently defeating the MANUAL override signal."""
    good_match = _make_supplier_product(
        session, _TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-GOOD", name="Test Widget 10mg (Vial)"
    )
    _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[1], sku="SKU-UNRELATED", name="Totally Different Item")
    variant = _make_variant(session, "manual-override", name="Test Widget 10mg (Vial)")

    # The admin deliberately picks the unrelated product, not the one
    # that actually matches this variant.
    mapping = admin_products.set_mapping(
        session,
        variant_id=variant.id,
        supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[1],
        actor="alice",
        action_label="mapping.approved",
    )

    assert mapping.match_confidence == "MANUAL"
    assert good_match.supplier_product_id != _TEST_SUPPLIER_PRODUCT_IDS[1]


def test_set_mapping_change_deactivates_previous_mapping(session):
    old_supplier = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-OLD", name="Old Widget")
    new_supplier = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[1], sku="SKU-NEW", name="New Widget")
    variant = _make_variant(session, "change")
    old_mapping = _make_mapping(session, variant, old_supplier)

    admin_products.set_mapping(
        session,
        variant_id=variant.id,
        supplier_product_id=new_supplier.supplier_product_id,
        actor="alice",
        action_label="mapping.changed",
    )
    session.refresh(old_mapping)

    assert old_mapping.is_active is False
    active = admin_products._pick_active_mapping(admin_products._get_mappings(session, variant.id))
    assert active is not None
    assert active.supplier_product_id == new_supplier.supplier_product_id

    audit = _audit_rows_for(session, variant.id)
    assert audit[-1].action == "mapping.changed"
    assert audit[-1].data["previous_supplier_product_id"] == old_supplier.supplier_product_id
    assert audit[-1].data["new_supplier_product_id"] == new_supplier.supplier_product_id


def test_unmap_deactivates_forces_unsellable_even_if_was_sellable_and_writes_audit_event(session):
    supplier_product = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-1", name="Widget 1")
    variant = _make_variant(session, "unmap")
    mapping = _make_mapping(session, variant, supplier_product)
    admin_products.enable(session, variant_id=variant.id, actor="alice")
    assert variant.is_sellable is True

    admin_products.unmap(session, variant_id=variant.id, actor="bob")
    session.refresh(mapping)

    assert mapping.is_active is False
    assert variant.is_sellable is False
    audit = _audit_rows_for(session, variant.id)
    assert audit[-1].action == "mapping.unmapped"
    assert audit[-1].data["previous_supplier_product_id"] == supplier_product.supplier_product_id


def test_unmap_raises_when_nothing_active_to_remove(session):
    variant = _make_variant(session, "unmap-nothing")
    with pytest.raises(admin_products.AdminActionError, match="no active mapping"):
        admin_products.unmap(session, variant_id=variant.id, actor="alice")


def test_list_admin_products_uses_persisted_confidence_for_mapped_variant(session):
    supplier_product = _make_supplier_product(
        session, _TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-1", name="Test Widget 10mg (Vial)"
    )
    variant = _make_variant(session, "list-mapped", name="Test Widget 10mg (Vial)")
    _make_mapping(session, variant, supplier_product, match_confidence="MANUAL")

    rows = admin_products.list_admin_products(session)
    row = next(r for r in rows if r.variant_id == variant.id)

    assert row.mapping_status == "MAPPED"
    assert row.confidence == "MANUAL"  # persisted, not recomputed
    assert row.supplier_sku == "SKU-1"


def test_list_admin_products_computes_live_candidate_for_unmapped_variant(session):
    _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-1", name="Test Widget 10mg (Vial)")
    variant = _make_variant(session, "list-unmapped", name="Test Widget 10mg (Vial)")

    rows = admin_products.list_admin_products(session)
    row = next(r for r in rows if r.variant_id == variant.id)

    assert row.mapping_status == "UNMAPPED"
    assert row.confidence is not None
    assert row.supplier_product_id == _TEST_SUPPLIER_PRODUCT_IDS[0]


def test_list_admin_products_shows_unmapped_not_stale_mapped_after_unmap(session):
    """Regression guard: a mapping row that's been deactivated by unmap()
    still has a persisted mapping_status of "MAPPED" (its historical
    value) — the admin list must not show that stale label as if
    unmapping did nothing."""
    supplier_product = _make_supplier_product(
        session, _TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-1", name="Test Widget 10mg (Vial)"
    )
    variant = _make_variant(session, "list-after-unmap", name="Test Widget 10mg (Vial)")
    _make_mapping(session, variant, supplier_product)

    admin_products.unmap(session, variant_id=variant.id, actor="alice")

    rows = admin_products.list_admin_products(session)
    row = next(r for r in rows if r.variant_id == variant.id)
    assert row.mapping_status == "UNMAPPED"
