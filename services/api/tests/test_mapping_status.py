from __future__ import annotations

import pytest
from sqlalchemy import text

from app.catalog_import.sync import _upsert_mapping
from app.db.session import SessionLocal
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping
from app.services.mapping_status import approve_mapping, get_mapping_status

_TEST_SUPPLIER_PRODUCT_IDS = [999201, 999202, 999203]
_TEST_SLUG_PREFIX = "test-mapping-status"


def _cleanup(session):
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
        raw_payload={"productId": supplier_product_id, "sku": sku, "name": name},
    )
    session.add(supplier_product)
    session.flush()
    return supplier_product


def _make_variant(session, slug_suffix: str, *, form="lyophilized"):
    product = Product(slug=f"{_TEST_SLUG_PREFIX}-{slug_suffix}", name="Test Widget", images=[], is_active=False)
    session.add(product)
    session.flush()
    variant = ProductVariant(
        product_id=product.id,
        sku=f"TC-TEST-MAPPING-STATUS-{slug_suffix.upper()}",
        name="Test Widget 10mg",
        retail_price_cents=1000,
        form=form,
    )
    session.add(variant)
    session.flush()
    return variant


def _make_mapping(session, variant, supplier_product, *, mapping_status: str = "MAPPED"):
    mapping = SupplierProductMapping(
        product_variant_id=variant.id,
        supplier_product_id=supplier_product.supplier_product_id,
        supplier_sku=supplier_product.supplier_sku,
        supplier_name=supplier_product.supplier_name,
        mapping_status=mapping_status,
    )
    session.add(mapping)
    session.flush()
    return mapping


def test_approve_mapping_moves_changed_back_to_mapped_and_refreshes_snapshot(session):
    supplier_product = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-OLD", name="Widget Old")
    variant = _make_variant(session, "approve")
    mapping = _make_mapping(session, variant, supplier_product, mapping_status="CHANGED")

    # The supplier data that caused CHANGED in the first place — approving
    # is itself the re-verification, so the snapshot should refresh too.
    supplier_product.supplier_sku = "SKU-NEW"
    supplier_product.supplier_name = "Widget New"
    session.flush()

    approve_mapping(session, mapping)
    session.flush()

    assert mapping.mapping_status == "MAPPED"
    assert mapping.supplier_sku == "SKU-NEW"
    assert mapping.supplier_name == "Widget New"
    assert get_mapping_status(session, variant.id) == "MAPPED"

    # Now that it's genuinely MAPPED again, the gate allows sellable.
    variant.is_sellable = True
    session.flush()
    assert variant.is_sellable is True


def test_catalog_reimport_does_not_silently_resurrect_a_changed_mapping(session):
    """Regression guard: re-running the price-sheet import must never be
    a backdoor around admin review. If reconciliation already marked a
    mapping CHANGED, _upsert_mapping must leave it untouched even when
    the row is re-encountered as an EXACT match during a re-import."""
    supplier_product = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[2], sku="SKU-STALE", name="Widget Stale")
    variant = _make_variant(session, "reimport")
    mapping = _make_mapping(session, variant, supplier_product, mapping_status="CHANGED")
    mapping.is_active = False
    session.flush()

    # Supplier data has since reverted back to matching — if _upsert_mapping
    # blindly refreshed on every EXACT reconfirmation, this would silently
    # flip mapping_status back to MAPPED with no admin involved.
    result = _upsert_mapping(session, product_variant_id=variant.id, supplier_product=supplier_product)
    session.flush()

    assert result.id == mapping.id
    assert result.mapping_status == "CHANGED"
    assert result.is_active is False
    assert get_mapping_status(session, variant.id) == "CHANGED"
