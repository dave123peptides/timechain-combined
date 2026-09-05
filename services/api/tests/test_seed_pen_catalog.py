"""Pure checks on the pen seed table — no database. The DB behaviour of
the script is exercised by running it (see README); these guard the data
itself: the shape the storefront's strength formatter expects, the
ascending-price invariant the PDP's variant order relies on, and the
category mapping the script stamps."""

from pathlib import Path

from app.constants.product_categories import PRODUCT_CATEGORY_BY_SLUG
from app.scripts.seed_pen_catalog import _PENS, SIZE_KEY_RE, variant_name, variant_sku

_PUBLIC = Path(__file__).resolve().parents[3] / "apps" / "web" / "public"


def test_table_matches_the_price_sheet_counts():
    # 51 sheet rows: 5 multi-size products (22 rows) + 29 single-size pens,
    # plus MT-II 10 mg added by David on 2026-09-05.
    assert len(_PENS) == 35
    assert sum(len(p.sizes) for p in _PENS) == 52


def test_slugs_and_skus_are_unique():
    slugs = [p.slug for p in _PENS]
    assert len(slugs) == len(set(slugs))
    skus = [variant_sku(p.slug, s.size_key) for p in _PENS for s in p.sizes]
    assert len(skus) == len(set(skus))
    assert all(len(sku) <= 100 for sku in skus)


def test_size_keys_are_bare_mg_numbers():
    for pen in _PENS:
        for size in pen.sizes:
            assert SIZE_KEY_RE.match(size.size_key), (pen.slug, size.size_key)


def test_prices_are_positive_and_strictly_ascending_within_a_product():
    # get_sellable_product_by_slug orders variants by price; the sheet's
    # sizes rise with price, so this is what keeps "1.5mg … 10mg" in order.
    for pen in _PENS:
        prices = [s.price_cents for s in pen.sizes]
        assert all(p > 0 for p in prices), pen.slug
        assert prices == sorted(prices) and len(set(prices)) == len(prices), pen.slug


def test_every_slug_has_a_category():
    for pen in _PENS:
        assert pen.slug in PRODUCT_CATEGORY_BY_SLUG, pen.slug


def test_decimal_sizes_format_with_mg():
    assert variant_name("GLP-1S (Semaglutide)", "1.5") == "GLP-1S (Semaglutide) 1.5mg pen"


def test_every_image_path_exists_in_the_web_public_folder():
    for pen in _PENS:
        for image in pen.images:
            assert image.startswith("/products/pens/"), image
            assert (_PUBLIC / image.lstrip("/")).is_file(), image
