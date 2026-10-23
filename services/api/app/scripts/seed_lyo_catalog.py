"""Manual entrypoint: python -m app.scripts.seed_lyo_catalog

The lyophilized vial catalog's source of truth on the combined site
(2026-10-22). `_VIALS` below is the vial site's "TimeChain RUO LYO -
Final Pricing 9.1.26" ladder (David's 2026-08-22 lyophilized-only line,
35 products, 48 vials), carried over verbatim from that site's
app.scripts.sync_lyo_catalog._LADDER. Prices are the 9.1.26 sheet; edit
here and rerun.

Why a seed and not a port of sync_lyo_catalog: on the vial site the
product rows came from a supplier price-sheet import and the three
follow-up scripts (sync_lyo_catalog, activate_pending_lyo_variants,
apply_lyo_vial_photos) only adjusted them. This site starts from an empty
database, so this script does what those four did between them, the same
way seed_pen_catalog does for pens.

One product row per compound (David, 2026-10-22): 29 of these slugs also
ship as pens. For those, seed_pen_catalog owns the product's name, tagline
and About overview (the TCP Guide copy); this script adds the lyophilized
variants, appends the vial photo to `images`, and fills in the structured
copy the pen seed leaves empty (key_points, research_areas, pairs_with,
faq from app.constants.lyo_content). The six vial-only compounds get the
whole vial entry. Each seed hides only strays of ITS OWN form and merges
`images`/`content`, so the two run in either order.

What one run does, idempotently:

- upserts a `Product` by slug (created only if the pen seed hasn't) and
  every lyophilized `ProductVariant` by SKU (name, price, size_key);
- for each variant that isn't sellable yet, creates an obviously-fake
  placeholder SupplierProduct ("PENDING-..." SKU, id far outside any real
  supplier id range) under the vial supplier key plus a MANUAL, MAPPED
  SupplierProductMapping, then flips is_sellable through
  ProductVariant._validate_is_sellable for real. Same pattern both
  ancestor sites used to go live before real supplier SKUs existed;
- sets is_sellable=False on any LYOPHILIZED variant whose SKU is not in
  the table.

Placeholder mappings self-expire by design: a real supplier catalog sync
(services/worker) would reconcile them as "missing" and flip the variants
back to unsellable. No sync runs on this site (FULFILLMENT_MODE=manual);
map real SKUs through /admin/products when they arrive.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select

from app.constants.lyo_content import LYO_CONTENT
from app.constants.product_categories import PRODUCT_CATEGORY_BY_SLUG
from app.db.session import SessionLocal
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping
from app.scripts.seed_pen_catalog import SIZE_KEY_RE, _next_placeholder_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LYO_FORM = "lyophilized"
_LYO_SUPPLIER_KEY = "nxgen"  # the lyophilized-vial supplier account (see SupplierProduct.supplier_key)


@dataclass(frozen=True)
class VialSize:
    size_key: str  # mg per vial: "10", "10/10/50"; "10mL" for BAC water
    price_cents: int  # retail, integer cents, 9.1.26 sheet


@dataclass(frozen=True)
class VialProduct:
    slug: str
    # Used only when the pen seed hasn't already created the row — for a
    # shared compound the pen name (with the GLP drug name in parentheses,
    # David 2026-09-05) stays.
    name: str
    sizes: tuple[VialSize, ...]
    # The vial site's photo for this product (apps/web/public/products).
    images: tuple[str, ...] = ()


def variant_sku(slug: str, size_key: str) -> str:
    # Same shape the vial site's importer produced, so a future port of
    # its rows lines up SKU for SKU.
    return f"TC-{slug.upper()}-LYOPHILIZED-{size_key.upper().replace('/', '-')}"[:100]


def variant_name(product_name: str, size_key: str) -> str:
    # A bare mg size is a lyophilized compound; anything else (BAC water's
    # "10mL") is a supply and is named by its volume alone.
    if SIZE_KEY_RE.match(size_key):
        return f"{product_name} {size_key}mg lyophilized vial"
    return f"{product_name} {size_key}"


def _vial(slug: str, name: str, image: str, *sizes: tuple[str, int]) -> VialProduct:
    return VialProduct(
        slug=slug,
        name=name,
        sizes=tuple(VialSize(size_key, price) for size_key, price in sizes),
        images=(f"/products/{image}",),
    )


# The 9.1.26 ladder. Photos: the real vial photography David added
# 2026-08-24 (<slug>-lyo.png) where it exists, otherwise the product
# photo the vial site showed for that slug.
_VIALS: tuple[VialProduct, ...] = (
    # TODO(attorney-review): GLP-class slugs stay code names so
    # lib/compliance.ts keeps them off every promotional surface.
    _vial("glp-1s", "GLP-1S (Semaglutide)", "glp-1s-lyo.png", ("10", 11900), ("20", 15900), ("50", 34900)),
    _vial("glp-2t", "GLP-2T (Tirzepatide)", "glp-2t-lyo.png", ("10", 9900), ("30", 20900), ("60", 34900), ("100", 50900)),
    _vial(
        "glp-3r",
        "GLP-3R (Retatrutide)",
        "glp-3r-lyo.png",
        ("10", 13900),
        ("20", 19900),
        ("30", 25900),
        ("60", 44900),
        ("100", 64900),
    ),
    _vial("tesamorelin", "Tesamorelin", "tesamorelin-lyo.png", ("10", 9900), ("32", 19900)),
    _vial("sermorelin", "Sermorelin", "sermorelin-lyo.png", ("10", 8900)),
    _vial("ipamorelin", "Ipamorelin", "ipamorelin-2.png", ("10", 7900)),
    _vial("tesamorelin-ipamorelin", "Tesamorelin / Ipamorelin", "tesamorelin-ipamorelin-lyo.png", ("10/10", 11900)),
    _vial("glow-bpc-157-tb-500-ghk", "GLOW (BPC-157 / TB-500 / GHK-Cu)", "glow-bpc-157-tb-500-ghk-1.png", ("10/10/50", 14900)),
    _vial(
        "klow-kpv-bpc-157-tb-500-ghk",
        "KLOW (KPV / BPC-157 / TB-500 / GHK-Cu)",
        "klow-kpv-bpc-157-tb-500-ghk-2.png",
        ("10/10/10/50", 19900),
    ),
    _vial("cjc-no-dac-ipamorelin", "CJC-1295 (no DAC) / Ipamorelin", "cjc-no-dac-ipamorelin-1.png", ("10/10", 9900)),
    _vial("bpc-157", "BPC-157", "bpc-157-2.png", ("10", 8900), ("20", 9900)),
    _vial("tb-500", "TB-500", "tb-500-lyo.png", ("10", 11900)),
    _vial("bpc-157-tb-500-wolverine", "BPC-157 / TB-500 (Wolverine)", "bpc-157-tb-500-wolverine-2.png", ("10/10", 12900)),
    _vial("hcg-6000-units", "HCG (6000 units)", "hcg-6000-units-lyo.png", ("3", 7900)),
    _vial("aod-9604", "AOD-9604", "aod-9604-lyo.png", ("5", 6900)),
    _vial("nad", "NAD+", "nad-lyo.png", ("500", 11900), ("1000", 14900)),
    _vial("pt-141", "PT-141", "pt-141-lyo.png", ("10", 5500)),
    _vial("igf1-lr3", "IGF-1 LR3", "igf1-lr3-1.jpg", ("1", 11900)),
    _vial("mots-c", "MOTS-C", "mots-c-lyo.png", ("10", 9900), ("20", 14900)),
    _vial("mt-1", "MT-1", "mt-1-1.jpg", ("10", 5500)),
    _vial("mt-2", "MT-II", "mt-2-1.jpg", ("10", 5500)),
    # TODO(attorney-review): see the GLP note above.
    _vial("cagrilinitide", "Cagrilinitide (Cagrilintide)", "cagrilinitide-2.png", ("10", 12900)),
    _vial("ghk-cu", "GHK-Cu", "ghk-cu-2.png", ("50", 5900)),
    _vial("ghk-cu-kpv", "GHK-Cu / KPV", "ghk-cu-kpv-lyo.png", ("50/10", 7900)),
    _vial("ghrp-2", "GHRP-2", "ghrp-2-lyo.png", ("10", 5200)),
    _vial("ghrp-6", "GHRP-6", "ghrp-6-lyo.png", ("10", 5200)),
    _vial("ta-1", "TA-1", "ta-1-1.jpg", ("10", 12900)),
    _vial("epithalon", "Epithalon", "epithalon-lyo.png", ("50", 15900)),
    _vial("kisspeptin", "Kisspeptin", "kisspeptin-lyo.png", ("5", 4900)),
    _vial("kpv", "KPV", "kpv-1.jpeg", ("10", 7900)),
    _vial("selank", "Selank", "selank-2.png", ("10", 6900)),
    _vial("semax", "Semax", "semax-2.png", ("10", 6900)),
    _vial("ss-31", "SS-31", "ss-31-lyo.png", ("50", 16500)),
    _vial("dsip", "DSIP", "dsip-1.jpg", ("5", 5500)),
    # $10 per David 9/2. A reconstitution supply, not a research compound:
    # no benefit group (lib/categories.ts) and never promoted.
    _vial("bac-water", "Bacteriostatic Reconstitution Water (BAC)", "bac-water-1.jpg", ("10mL", 1000)),
)


def _activate(session, variant: ProductVariant, supplier_name: str) -> None:
    """Give the variant a placeholder MAPPED mapping under the vial
    supplier key (if it has none) and set is_sellable through the
    validator. Mirrors seed_pen_catalog._activate."""
    has_mapping = any(m.mapping_status == "MAPPED" and m.is_active for m in variant.supplier_mappings)
    if not has_mapping:
        supplier_product = SupplierProduct(
            supplier_product_id=_next_placeholder_id(session),
            supplier_key=_LYO_SUPPLIER_KEY,
            supplier_sku=f"PENDING-{variant.sku}",
            supplier_name=supplier_name,
            supplier_active=True,
            raw_payload={"placeholder": True, "reason": "seed_lyo_catalog", "sheet_name": supplier_name},
        )
        session.add(supplier_product)
        session.flush()
        session.add(
            SupplierProductMapping(
                product_variant_id=variant.id,
                supplier_product_id=supplier_product.supplier_product_id,
                supplier_key=_LYO_SUPPLIER_KEY,
                supplier_sku=supplier_product.supplier_sku,
                supplier_name=supplier_product.supplier_name,
                mapping_status="MAPPED",
                match_confidence="MANUAL",
            )
        )
        session.flush()
        session.refresh(variant)
    variant.is_sellable = True


def _merge_content(existing: dict | None, vial_content: dict) -> dict:
    """The vial copy fills whatever the row doesn't already have; keys the
    pen seed set (its overview) win."""
    merged = dict(vial_content)
    for key, value in (existing or {}).items():
        if value:
            merged[key] = value
    return merged


def seed_lyo_catalog(session=None) -> dict[str, int]:
    owns_session = session is None
    session = session or SessionLocal()
    counts = {"products_created": 0, "variants_created": 0, "activated": 0, "hidden": 0}
    try:
        seeded_skus: set[str] = set()
        for vial in _VIALS:
            description, content = LYO_CONTENT[vial.slug]
            product = session.execute(select(Product).where(Product.slug == vial.slug)).scalar_one_or_none()
            if product is None:
                product = Product(slug=vial.slug, name=vial.name, description=description, images=[], is_active=True)
                session.add(product)
                counts["products_created"] += 1
            if not product.description:
                product.description = description
            product.content = _merge_content(product.content, content)
            # Vial photo after whatever is already there (the pen renders);
            # never duplicated on a rerun.
            product.images = list(product.images or []) + [img for img in vial.images if img not in (product.images or [])]
            product.category = PRODUCT_CATEGORY_BY_SLUG[vial.slug]
            product.is_active = True
            session.flush()

            for size in vial.sizes:
                sku = variant_sku(vial.slug, size.size_key)
                seeded_skus.add(sku)
                variant = session.execute(select(ProductVariant).where(ProductVariant.sku == sku)).scalar_one_or_none()
                if variant is None:
                    variant = ProductVariant(
                        product_id=product.id,
                        sku=sku,
                        name=variant_name(product.name, size.size_key),
                        retail_price_cents=size.price_cents,
                        size_key=size.size_key,
                        form=LYO_FORM,
                    )
                    session.add(variant)
                    session.flush()
                    counts["variants_created"] += 1
                variant.product_id = product.id
                variant.name = variant_name(product.name, size.size_key)
                variant.retail_price_cents = size.price_cents
                variant.size_key = size.size_key
                variant.form = LYO_FORM
                if not variant.is_sellable:
                    _activate(session, variant, variant.name)
                    counts["activated"] += 1
            session.flush()

        strays = session.execute(
            select(ProductVariant).where(
                ProductVariant.is_sellable.is_(True),
                ProductVariant.form == LYO_FORM,
                ProductVariant.sku.not_in(seeded_skus),
            )
        ).scalars()
        for variant in strays:
            variant.is_sellable = False
            counts["hidden"] += 1

        session.commit()
        logger.info("seed_lyo_catalog: %s", counts)
        return counts
    finally:
        if owns_session:
            session.close()


if __name__ == "__main__":
    seed_lyo_catalog()
