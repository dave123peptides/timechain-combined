"""CATALOG_PRICES_PUBLIC (David, 2026-10-22): no prices on the site until
the wholesale sheet exists. Off, every price field on the public catalog
endpoints is null; the data itself is untouched."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping

client = TestClient(app)

_SLUG = "test-catalog-prices"
_SUPPLIER_ID = 998_300


def _cleanup(session):
    session.execute(text("DELETE FROM products WHERE slug = :slug"), {"slug": _SLUG})
    session.execute(text("DELETE FROM supplier_products WHERE supplier_product_id = :id"), {"id": _SUPPLIER_ID})
    session.commit()


@pytest.fixture
def sellable_slug():
    db = SessionLocal()
    _cleanup(db)
    product = Product(slug=_SLUG, name="Test Priced Compound", images=[], is_active=True)
    db.add(product)
    db.flush()
    variant = ProductVariant(
        product_id=product.id, sku="TC-TEST-PRICES-10", name="Test Priced Compound 10mg", retail_price_cents=4200, form="pen", size_key="10"
    )
    db.add(variant)
    db.flush()
    supplier = SupplierProduct(
        supplier_product_id=_SUPPLIER_ID, supplier_sku="TEST-PRICES", supplier_name="Test supplier row", supplier_active=True, raw_payload={}
    )
    db.add(supplier)
    db.flush()
    db.add(
        SupplierProductMapping(
            product_variant_id=variant.id,
            supplier_product_id=_SUPPLIER_ID,
            supplier_sku="TEST-PRICES",
            supplier_name="Test supplier row",
            mapping_status="MAPPED",
        )
    )
    db.flush()
    variant.is_sellable = True
    db.commit()
    yield _SLUG
    _cleanup(db)
    db.close()


def test_switch_defaults_off():
    assert Settings(_env_file=None).catalog_prices_public is False


def test_prices_are_null_when_hidden(sellable_slug, monkeypatch):
    monkeypatch.setattr(get_settings(), "catalog_prices_public", False)
    products = [p for p in client.get("/shop/products", params={"q": sellable_slug}).json() if p["slug"] == sellable_slug]
    assert len(products) == 1
    assert products[0]["starting_price_cents"] is None
    assert all(v["price_cents"] is None for v in products[0]["variants"])
    detail = client.get(f"/shop/products/{sellable_slug}").json()
    assert all(v["price_cents"] is None for v in detail["variants"])


def test_prices_present_when_public(sellable_slug, monkeypatch):
    monkeypatch.setattr(get_settings(), "catalog_prices_public", True)
    products = [p for p in client.get("/shop/products", params={"q": sellable_slug}).json() if p["slug"] == sellable_slug]
    assert products[0]["starting_price_cents"] == 4200
    detail = client.get(f"/shop/products/{sellable_slug}").json()
    assert detail["variants"][0]["price_cents"] == 4200
