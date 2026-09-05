from __future__ import annotations

import itertools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal
from app.main import app
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping
from app.services import storefront

_TEST_SLUG_PREFIX = "test-search"
# Narrow, non-overlapping band. test_storefront.py starts at 999401 and
# test_payments.py at 999501, but both clean up with
# `BETWEEN start AND start + 9999`, so their ranges already overlap each
# other — it only survives because pytest runs files serially and each
# cleans on both entry and exit. Don't widen this one into theirs.
_TEST_SUPPLIER_PRODUCT_ID_START = 999601
_supplier_product_id_counter = itertools.count(_TEST_SUPPLIER_PRODUCT_ID_START)


def _cleanup(session):
    session.execute(text("DELETE FROM products WHERE slug LIKE :prefix"), {"prefix": f"{_TEST_SLUG_PREFIX}%"})
    # Bounded, not `>=`: real AllianceTek supplier_product_ids are much
    # larger 8-digit numbers, and an unbounded delete here would take out
    # real supplier catalog rows.
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


def _make_sellable_product(session, slug_suffix, name, *, price_cents=10000, description=None, category=None):
    """A product with exactly one sellable variant, so list_sellable_products
    returns it. is_sellable is set via raw SQL to bypass
    ProductVariant._validate_is_sellable — this file tests the search and
    sort behaviour of the query, not the validator (test_sellable_guard.py
    owns that)."""
    product = Product(
        slug=f"{_TEST_SLUG_PREFIX}-{slug_suffix}",
        name=name,
        description=description,
        category=category,
        images=[],
        is_active=False,
    )
    session.add(product)
    session.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku=f"TC-TEST-SEARCH-{slug_suffix.upper()}",
        name=f"{name} 10mg",
        retail_price_cents=price_cents,
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
    session.execute(text("UPDATE product_variants SET is_sellable = true WHERE id = :id"), {"id": variant.id})
    session.commit()
    return product


def _slugs(summaries):
    return {s.slug for s in summaries}


def test_q_matches_name_case_insensitively(session):
    _make_sellable_product(session, "alpha", "Zeta Compound")
    _make_sellable_product(session, "beta", "Omega Compound")

    for term in ("zeta", "ZETA", "ZeTa"):
        found = _slugs(storefront.list_sellable_products(session, q=term))
        assert f"{_TEST_SLUG_PREFIX}-alpha" in found
        assert f"{_TEST_SLUG_PREFIX}-beta" not in found


def test_q_matches_slug(session):
    _make_sellable_product(session, "alpha", "Zeta Compound")
    _make_sellable_product(session, "beta", "Omega Compound")

    found = _slugs(storefront.list_sellable_products(session, q=f"{_TEST_SLUG_PREFIX}-beta"))
    assert found == {f"{_TEST_SLUG_PREFIX}-beta"}


def test_q_matches_description(session):
    # description is NULL for every real product until
    # app.scripts.sync_product_content runs, so this clause is currently
    # inert in production — but it must work the moment content lands.
    _make_sellable_product(session, "alpha", "Zeta Compound", description="A distinctive marker phrase.")
    _make_sellable_product(session, "beta", "Omega Compound")

    found = _slugs(storefront.list_sellable_products(session, q="distinctive marker"))
    assert found == {f"{_TEST_SLUG_PREFIX}-alpha"}


def test_q_escapes_ilike_wildcards(session):
    """A bare '%' must not match the entire catalog.

    This is the whole reason _escape_like exists: unescaped, '%' becomes a
    LIKE wildcard and the search box silently returns everything while
    appearing to filter.
    """
    _make_sellable_product(session, "alpha", "100% Pure Test Compound")
    _make_sellable_product(session, "beta", "Omega Compound")

    # '%' is treated as the literal character, so it matches only the
    # product whose name actually contains one — NOT the whole catalog.
    # Asserting the exclusion is the point: an unescaped '%' would return
    # beta (and every real product) too.
    percent = _slugs(storefront.list_sellable_products(session, q="%"))
    assert f"{_TEST_SLUG_PREFIX}-alpha" in percent
    assert f"{_TEST_SLUG_PREFIX}-beta" not in percent

    # '_' would be a single-character wildcard unescaped; neither test
    # product contains a literal underscore in name, slug or description.
    assert storefront.list_sellable_products(session, q="_") == []

    # The literal string "100%" should still find the product named with it.
    assert _slugs(storefront.list_sellable_products(session, q="100%")) == {f"{_TEST_SLUG_PREFIX}-alpha"}


def test_q_blank_is_ignored(session):
    _make_sellable_product(session, "alpha", "Zeta Compound")

    baseline = _slugs(storefront.list_sellable_products(session))
    for blank in ("", "   ", "\t"):
        assert _slugs(storefront.list_sellable_products(session, q=blank)) == baseline


def test_q_combines_with_category_filter(session):
    _make_sellable_product(session, "alpha", "Zeta Compound", category="Test Category A")
    _make_sellable_product(session, "beta", "Zeta Variant", category="Test Category B")

    found = _slugs(storefront.list_sellable_products(session, q="zeta", category="Test Category A"))
    assert found == {f"{_TEST_SLUG_PREFIX}-alpha"}

    assert storefront.list_sellable_products(session, q="zeta", category="Nonexistent Category") == []


def test_sort_price_asc_and_desc(session):
    _make_sellable_product(session, "cheap", "Zeta Cheap", price_cents=1000)
    _make_sellable_product(session, "dear", "Zeta Dear", price_cents=9000)

    asc = storefront.list_sellable_products(session, q="zeta", sort="price_asc")
    assert [s.starting_price_cents for s in asc] == [1000, 9000]

    desc = storefront.list_sellable_products(session, q="zeta", sort="price_desc")
    assert [s.starting_price_cents for s in desc] == [9000, 1000]


def test_sort_unknown_value_falls_back_to_name(session):
    _make_sellable_product(session, "cheap", "Zeta Cheap", price_cents=9000)
    _make_sellable_product(session, "dear", "Alpha Dear", price_cents=1000)

    by_name = storefront.list_sellable_products(session, q="test-search", sort="name")
    fallback = storefront.list_sellable_products(session, q="test-search", sort="bogus-sort-key")
    none_sort = storefront.list_sellable_products(session, q="test-search", sort=None)

    assert [s.slug for s in fallback] == [s.slug for s in by_name]
    assert [s.slug for s in none_sort] == [s.slug for s in by_name]


def test_route_tolerates_hostile_query_params(session):
    """A public catalog URL must never 422 or 500 on a hand-typed value.

    `sort` is intentionally not a Literal for this reason, and `q` is
    escaped rather than rejected.
    """
    _make_sellable_product(session, "alpha", "Zeta Compound")

    with TestClient(app) as client:
        response = client.get("/shop/products", params={"q": "%", "sort": "bogus-sort-key"})
        assert response.status_code == 200
        # Not asserting an empty list: that would depend on no product in
        # the real catalog ever having a '%' in its name. What matters is
        # that '%' is not a wildcard, so a product without one is excluded.
        assert all(item["slug"] != f"{_TEST_SLUG_PREFIX}-alpha" for item in response.json())

        response = client.get("/shop/products", params={"q": "zeta"})
        assert response.status_code == 200
        assert any(item["slug"] == f"{_TEST_SLUG_PREFIX}-alpha" for item in response.json())
