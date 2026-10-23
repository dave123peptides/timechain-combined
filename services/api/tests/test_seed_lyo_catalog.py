"""Pure checks on the vial seed table — no database. The DB behaviour of
the script is exercised by running it (see README); these guard the data
itself, mirroring tests/test_seed_pen_catalog.py: the 9.1.26 ladder's
shape, the ascending-price invariant the PDP's variant order relies on,
the category and copy lookups the script performs, and the photos it
references."""

from pathlib import Path

from app.constants.lyo_content import LYO_CONTENT
from app.constants.product_categories import PRODUCT_CATEGORY_BY_SLUG
from app.scripts.seed_lyo_catalog import _VIALS, variant_name, variant_sku
from app.scripts.seed_pen_catalog import _PENS, SIZE_KEY_RE

_PUBLIC = Path(__file__).resolve().parents[3] / "apps" / "web" / "public"


def test_table_matches_the_ladder_counts():
    # The vial site's _LADDER (9.1.26 sheet) less BAC water, dropped
    # 2026-10-23: 34 products, 47 vials.
    assert len(_VIALS) == 34
    assert sum(len(v.sizes) for v in _VIALS) == 47


def test_slugs_and_skus_are_unique_and_never_collide_with_pen_skus():
    slugs = [v.slug for v in _VIALS]
    assert len(slugs) == len(set(slugs))
    skus = [variant_sku(v.slug, s.size_key) for v in _VIALS for s in v.sizes]
    assert len(skus) == len(set(skus))
    assert all(len(sku) <= 100 for sku in skus)
    assert all("-LYOPHILIZED-" in sku for sku in skus)


def test_size_keys_are_bare_mg_numbers():
    for vial in _VIALS:
        for size in vial.sizes:
            assert SIZE_KEY_RE.match(size.size_key), (vial.slug, size.size_key)


def test_bac_water_is_not_sold():
    assert all(v.slug != "bac-water" for v in _VIALS)


def test_prices_are_positive_and_strictly_ascending_within_a_product():
    for vial in _VIALS:
        prices = [s.price_cents for s in vial.sizes]
        assert all(p > 0 for p in prices), vial.slug
        assert prices == sorted(prices) and len(set(prices)) == len(prices), vial.slug


def test_every_slug_has_a_category_and_vial_copy():
    for vial in _VIALS:
        assert vial.slug in PRODUCT_CATEGORY_BY_SLUG, vial.slug
        assert vial.slug in LYO_CONTENT, vial.slug


def test_shared_compounds_use_the_pen_seed_name():
    """One product row per compound: where both seeds know a slug, the
    name here must match the pen seed's so neither run renames the row."""
    pen_names = {p.slug: p.name for p in _PENS}
    shared = [v for v in _VIALS if v.slug in pen_names]
    assert len(shared) == 29
    for vial in shared:
        assert vial.name == pen_names[vial.slug], vial.slug


def test_vial_only_compounds_are_the_expected_five():
    pen_slugs = {p.slug for p in _PENS}
    assert sorted(v.slug for v in _VIALS if v.slug not in pen_slugs) == [
        "aod-9604",
        "ghk-cu-kpv",
        "ghrp-2",
        "ghrp-6",
        "mt-1",
    ]


def test_variant_names_format_strength():
    assert variant_name("BPC-157", "10") == "BPC-157 10mg lyophilized vial"
    # A supply, not a lyophilized compound: named by volume only.
    assert variant_name("Bacteriostatic Reconstitution Water (BAC)", "10mL") == (
        "Bacteriostatic Reconstitution Water (BAC) 10mL"
    )


def test_every_image_path_exists_in_the_web_public_folder():
    for vial in _VIALS:
        assert vial.images, vial.slug
        for image in vial.images:
            assert image.startswith("/products/") and not image.startswith("/products/pens/"), image
            assert (_PUBLIC / image.lstrip("/")).is_file(), image
