from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping
from app.services.mapping_status import get_mapping_status

# Clearly-fake, high-numbered IDs / a distinctive slug prefix so cleanup
# never touches real data, same pattern as
# services/worker/tests/test_supplier_sync.py's _TEST_SUPPLIER_PRODUCT_IDS.
_TEST_SUPPLIER_PRODUCT_IDS = [999101, 999102, 999103, 999104, 999105]
_TEST_SLUG_PREFIX = "test-sellable-guard"


def _cleanup(session):
    session.execute(
        text("DELETE FROM products WHERE slug LIKE :prefix"), {"prefix": f"{_TEST_SLUG_PREFIX}%"}
    )
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


def _make_variant(session, slug_suffix: str, *, form="pen"):
    product = Product(slug=f"{_TEST_SLUG_PREFIX}-{slug_suffix}", name="Test Widget", images=[], is_active=False)
    session.add(product)
    session.flush()
    variant = ProductVariant(
        product_id=product.id,
        sku=f"TC-TEST-SELLABLE-GUARD-{slug_suffix.upper()}",
        name="Test Widget 10mg",
        retail_price_cents=1000,
        form=form,
    )
    session.add(variant)
    session.flush()
    return variant


def _make_mapping(session, variant, supplier_product, *, is_active: bool = True):
    mapping = SupplierProductMapping(
        product_variant_id=variant.id,
        supplier_product_id=supplier_product.supplier_product_id,
        supplier_sku=supplier_product.supplier_sku,
        supplier_name=supplier_product.supplier_name,
        is_active=is_active,
    )
    session.add(mapping)
    session.flush()
    return mapping


def test_mapping_status_missing_when_no_mapping_row_exists(session):
    """Also covers every pre-mapping review state (LIKELY, AMBIGUOUS,
    NO_MATCH/UNMAPPED) — none of them ever create a mapping row, so
    there's nothing at the DB level to distinguish "never reviewed" from
    "reviewed but not confident enough"; both are MISSING."""
    variant = _make_variant(session, "missing")
    assert get_mapping_status(session, variant.id) == "MISSING"

    with pytest.raises(ValueError, match="MISSING"):
        variant.is_sellable = True


def test_mapping_status_mapped_when_verified_and_current(session):
    supplier_product = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-1", name="Widget 10mg")
    variant = _make_variant(session, "mapped")
    _make_mapping(session, variant, supplier_product)

    assert get_mapping_status(session, variant.id) == "MAPPED"

    variant.is_sellable = True
    session.flush()
    assert variant.is_sellable is True


def test_mapping_status_changed_when_mapping_deactivated(session):
    supplier_product = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[1], sku="SKU-2", name="Widget 20mg")
    variant = _make_variant(session, "deactivated")
    _make_mapping(session, variant, supplier_product, is_active=False)

    assert get_mapping_status(session, variant.id) == "CHANGED"

    with pytest.raises(ValueError, match="CHANGED"):
        variant.is_sellable = True


def test_mapping_status_changed_when_reconciliation_marked_it_changed(session):
    """Live drift detection (supplier renamed/re-SKU'd/deactivated a
    product) now happens once, reactively, in
    worker/supplier_sync/reconciliation.py at sync time — not here.
    get_mapping_status just reads whatever that step already persisted;
    this simulates its result directly."""
    supplier_product = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[2], sku="SKU-3", name="Widget 30mg")
    variant = _make_variant(session, "changed")
    mapping = _make_mapping(session, variant, supplier_product)

    mapping.mapping_status = "CHANGED"
    session.flush()

    assert get_mapping_status(session, variant.id) == "CHANGED"
    with pytest.raises(ValueError, match="CHANGED"):
        variant.is_sellable = True


def test_mapping_status_missing_when_reconciliation_marked_it_missing(session):
    """The supplier product disappeared from the feed entirely — the
    mapping row still exists (never deleted, FK is RESTRICT), but its
    persisted status says MISSING, same bucket as never having been
    mapped at all for the purposes of the sellable gate."""
    supplier_product = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[3], sku="SKU-4", name="Widget 40mg")
    variant = _make_variant(session, "disappeared")
    mapping = _make_mapping(session, variant, supplier_product)

    mapping.mapping_status = "MISSING"
    session.flush()

    assert get_mapping_status(session, variant.id) == "MISSING"
    with pytest.raises(ValueError, match="MISSING"):
        variant.is_sellable = True


def test_setting_is_sellable_false_is_always_allowed(session):
    supplier_product = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[4], sku="SKU-5", name="Widget 50mg")
    variant = _make_variant(session, "toggle-off")
    _make_mapping(session, variant, supplier_product)

    variant.is_sellable = True
    session.flush()

    # Turning sellable back off never needs to re-verify mapping status.
    variant.is_sellable = False
    session.flush()
    assert variant.is_sellable is False


def test_lyophilized_variant_can_be_sellable_when_mapped(session):
    """The combined site sells both ancestor lines: a verified MAPPED
    lyophilized vial is sellable exactly like a pen (the pens site
    blocked it; the vial site blocked pens)."""
    supplier_product = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-LYO", name="Widget Lyo 10mg")
    variant = _make_variant(session, "lyo", form="lyophilized")
    _make_mapping(session, variant, supplier_product)

    assert get_mapping_status(session, variant.id) == "MAPPED"
    variant.is_sellable = True
    session.flush()
    assert variant.is_sellable is True


def test_lyophilized_variant_still_needs_a_mapped_supplier_row(session):
    """Allowing the form must not weaken the mapping gate for it."""
    variant = _make_variant(session, "lyo-unmapped", form="lyophilized")
    with pytest.raises(ValueError, match="MISSING"):
        variant.is_sellable = True


@pytest.mark.parametrize("form", ["vial", "preconstituted", "rx_vial", "other"])
def test_other_forms_can_never_be_sellable_even_when_verified_mapped(session, form):
    """Neither ancestor site sold these (plain/pre-constituted/rx vials
    and the importer's catch-all), so a verified MAPPED mapping must not
    be enough. The check runs before the mapping check, so the message
    names the form, not the status."""
    supplier_product = _make_supplier_product(session, _TEST_SUPPLIER_PRODUCT_IDS[1], sku=f"SKU-{form}", name=f"Widget {form} 10mg")
    variant = _make_variant(session, f"blocked-{form.replace('_', '-')}", form=form)
    _make_mapping(session, variant, supplier_product)

    assert get_mapping_status(session, variant.id) == "MAPPED"
    with pytest.raises(ValueError, match=f"form {form!r} is not sold"):
        variant.is_sellable = True


def test_sellable_forms_constant_is_exactly_pens_and_lyophilized():
    from app.models.catalog import SELLABLE_FORMS

    assert set(SELLABLE_FORMS) == {"pen", "lyophilized"}


def test_is_sellable_true_on_unattached_variant_raises():
    """A variant not yet added to any session has no way to verify its
    mapping status — must fail closed, not silently allow it."""
    variant = ProductVariant(sku="TC-TEST-UNATTACHED", name="Unattached Widget", retail_price_cents=500, form="pen")
    with pytest.raises(ValueError, match="session"):
        variant.is_sellable = True
