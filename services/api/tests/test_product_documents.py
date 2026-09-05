from __future__ import annotations

import dataclasses
import itertools
from datetime import date

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.catalog import (
    Product,
    ProductCoa,
    ProductVariant,
    SupplierProduct,
    SupplierProductMapping,
)
from app.services import storefront

_TEST_SLUG_PREFIX = "test-docs"
# Narrow band; see the note in test_storefront_search.py about the
# pre-existing overlap between test_storefront.py and test_payments.py.
_TEST_SUPPLIER_PRODUCT_ID_START = 999701
_supplier_product_id_counter = itertools.count(_TEST_SUPPLIER_PRODUCT_ID_START)
_TEST_CODE_PREFIX = "TST"
_code_counter = itertools.count(1)


def _cleanup(session):
    # product_coas cascades from products (ON DELETE CASCADE).
    session.execute(text("DELETE FROM products WHERE slug LIKE :prefix"), {"prefix": f"{_TEST_SLUG_PREFIX}%"})
    session.execute(
        text("DELETE FROM supplier_products WHERE supplier_product_id BETWEEN :start AND :end"),
        {"start": _TEST_SUPPLIER_PRODUCT_ID_START, "end": _TEST_SUPPLIER_PRODUCT_ID_START + 99},
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


def _make_product(session, slug_suffix, *, sellable=True, sds_url=None):
    product = Product(
        slug=f"{_TEST_SLUG_PREFIX}-{slug_suffix}",
        name=f"Test Doc Product {slug_suffix}",
        images=[],
        is_active=False,
        sds_url=sds_url,
    )
    session.add(product)
    session.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku=f"TC-TEST-DOCS-{slug_suffix.upper()}",
        name=f"{product.name} 10mg",
        retail_price_cents=10000,
        form="lyophilized",
        size_key="10",
    )
    session.add(variant)
    session.flush()

    supplier_product_id = next(_supplier_product_id_counter)
    session.add(
        SupplierProduct(
            supplier_product_id=supplier_product_id,
            supplier_sku=f"TEST-{supplier_product_id}",
            supplier_name=f"Test Supplier Product {supplier_product_id}",
            supplier_active=True,
            raw_payload={"productId": supplier_product_id},
        )
    )
    session.flush()
    session.add(
        SupplierProductMapping(
            product_variant_id=variant.id,
            supplier_product_id=supplier_product_id,
            supplier_sku=f"TEST-{supplier_product_id}",
            supplier_name=f"Test Supplier Product {supplier_product_id}",
            mapping_status="MAPPED",
        )
    )
    session.flush()
    if sellable:
        session.execute(text("UPDATE product_variants SET is_sellable = true WHERE id = :id"), {"id": variant.id})
    session.commit()
    return product


def _add_coa(session, product, *, strength, issued_on, lot="LOT-1", is_published=True, tests=None):
    n = next(_code_counter)
    code = f"{_TEST_CODE_PREFIX}{n:d}-{n:04d}"[:20]
    session.add(
        ProductCoa(
            product_id=product.id,
            verify_code=code,
            strength=strength,
            lot=lot,
            issued_on=issued_on,
            lab="Test Lab",
            client="Test Client",
            tests=tests if tests is not None else ["Identity", "Purity (HPLC)"],
            pdf_url=f"https://example.invalid/coa/{code}.pdf",
            verify_url=f"https://example.invalid/verify/{code}",
            source_file=f"{lot}__SKU__{code}.pdf",
            is_published=is_published,
        )
    )
    session.commit()
    return code


def test_detail_lists_published_coas_in_lab_report_order(session):
    """Strength ascending by number (not string — "100" must not sort
    before "20"), then newest certificate first within a strength."""
    product = _make_product(session, "order")
    c_20_old = _add_coa(session, product, strength="20", issued_on=date(2026, 5, 1))
    c_100 = _add_coa(session, product, strength="100", issued_on=date(2026, 6, 1))
    c_10 = _add_coa(session, product, strength="10", issued_on=date(2026, 4, 1))
    c_20_new = _add_coa(session, product, strength="20", issued_on=date(2026, 7, 1))

    detail = storefront.get_sellable_product_by_slug(session, product.slug)
    assert detail is not None
    assert [c.verify_code for c in detail.coas] == [c_10, c_20_new, c_20_old, c_100]
    first = detail.coas[0]
    assert first.strength == "10"
    assert first.lot == "LOT-1"
    assert first.lab == "Test Lab"
    assert first.tests == ["Identity", "Purity (HPLC)"]
    assert first.pdf_url.endswith(f"{c_10}.pdf")
    assert first.verify_url is not None
    # Customer-safe surface only: who the lab issued it to and the
    # original filename never leave the database.
    assert not hasattr(first, "client")
    assert not hasattr(first, "source_file")


def test_unpublished_coas_never_reach_the_storefront(session):
    product = _make_product(session, "hidden")
    shown = _add_coa(session, product, strength="10", issued_on=date(2026, 6, 1))
    _add_coa(session, product, strength="10", issued_on=date(2026, 7, 1), is_published=False)

    detail = storefront.get_sellable_product_by_slug(session, product.slug)
    assert [c.verify_code for c in detail.coas] == [shown]

    summary = next(s for s in storefront.list_sellable_products(session) if s.slug == product.slug)
    assert summary.coa_count == 1
    assert summary.coa_latest_issued_on == date(2026, 6, 1)

    index = {e.slug: e for e in storefront.list_published_coas(session)}
    assert [c.verify_code for c in index[product.slug].coas] == [shown]


def test_detail_with_no_coas_is_the_honest_empty_state(session):
    """Three catalog products hold no certificate today; the PDP renders
    "available on request" from an empty list, so it must come through
    as exactly that — not None, not an error."""
    _make_product(session, "none", sds_url=None)

    detail = storefront.get_sellable_product_by_slug(session, f"{_TEST_SLUG_PREFIX}-none")
    assert detail is not None
    assert detail.coas == []
    assert detail.sds_url is None

    summary = next(s for s in storefront.list_sellable_products(session) if s.slug == detail.slug)
    assert summary.coa_count == 0
    assert summary.coa_latest_issued_on is None
    assert summary.sds_url is None


def test_summary_rollup_counts_and_latest_date(session):
    """ProductCard's badge and /coa read the summary; it must carry the
    count and the newest date without the certificates themselves."""
    product = _make_product(session, "rollup")
    _add_coa(session, product, strength="10", issued_on=date(2026, 3, 1))
    _add_coa(session, product, strength="20", issued_on=date(2026, 8, 15))
    _add_coa(session, product, strength="20", issued_on=date(2026, 5, 1))

    summary = next(s for s in storefront.list_sellable_products(session) if s.slug == product.slug)
    assert summary.coa_count == 3
    assert summary.coa_latest_issued_on == date(2026, 8, 15)
    assert not hasattr(summary, "coas")


def test_sds_url_still_flows_through_summary_and_detail(session):
    _make_product(session, "sds", sds_url="https://example.invalid/sds.pdf")

    detail = storefront.get_sellable_product_by_slug(session, f"{_TEST_SLUG_PREFIX}-sds")
    assert detail.sds_url == "https://example.invalid/sds.pdf"
    summary = next(s for s in storefront.list_sellable_products(session) if s.slug == detail.slug)
    assert summary.sds_url == "https://example.invalid/sds.pdf"


def test_coa_index_only_lists_sellable_products_with_certificates(session):
    listed = _make_product(session, "index-listed")
    _add_coa(session, listed, strength="10", issued_on=date(2026, 6, 1))
    empty = _make_product(session, "index-empty")
    delisted = _make_product(session, "index-delisted", sellable=False)
    _add_coa(session, delisted, strength="10", issued_on=date(2026, 6, 1))

    slugs = {e.slug for e in storefront.list_published_coas(session)}
    assert listed.slug in slugs
    assert empty.slug not in slugs
    assert delisted.slug not in slugs


def test_storefront_dataclasses_expose_document_fields():
    """Guards the multi-layer plumbing: it is easy to add a column and
    the response model but forget one of the dataclass constructors,
    which fails silently as a permanent empty state."""
    summary_fields = {f.name for f in dataclasses.fields(storefront.StorefrontProductSummary)}
    assert {"coa_count", "coa_latest_issued_on", "sds_url"} <= summary_fields
    assert "coa_url" not in summary_fields
    detail_fields = {f.name for f in dataclasses.fields(storefront.StorefrontProductDetail)}
    assert {"coas", "sds_url"} <= detail_fields
    assert "coa_url" not in detail_fields
