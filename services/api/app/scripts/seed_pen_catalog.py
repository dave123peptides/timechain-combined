"""Manual entrypoint: python -m app.scripts.seed_pen_catalog

The pen catalog's source of truth. This storefront (TCP, forked from the
TimeChain vial site on 2026-09-05) sells pre-filled 3 mL auto-injector
pens only; `_PENS` below is David's 2026-09-05 pen price sheet, one
entry per product, one `PenSize` per purchasable pen.

What one run does, idempotently:

- upserts every `Product` by slug (name, tagline, content, images,
  category from PRODUCT_CATEGORY_BY_SLUG, is_active) and every
  `ProductVariant` by SKU (name, price, size_key, form="pen");
- for each variant that isn't sellable yet, creates an obviously-fake
  placeholder SupplierProduct ("PENDING-..." SKU, id far outside any
  real supplier id range) plus a MANUAL, MAPPED SupplierProductMapping,
  then flips is_sellable through ProductVariant._validate_is_sellable
  for real rather than bypassing it — the same pattern the vial site
  used to go live before real supplier SKUs existed. The sheet's own row
  name ("Semaglutide Month 1") is kept on that placeholder supplier row
  so it reaches the fulfillment spreadsheet's `items` column without ever
  appearing on the storefront;
- sets is_sellable=False on any variant whose SKU is not in the table.

Public labels are strength-only ("1.5mg"): "Month N" reads as a human
titration schedule, the consumer-use signal the compliance rules avoid.
GLP-class products keep their code-name slugs (lib/compliance.ts keeps
them off every promotional surface) but display the real name in
parentheses per David's 2026-09-05 decision — TODO(attorney-review).

Placeholder supplier mappings self-expire by design: a real supplier
catalog sync (services/worker) would reconcile them as "missing" and
flip the variants back to unsellable. No sync runs on this site
(FULFILLMENT_MODE=manual); when real pen supplier SKUs arrive, map them
through /admin/products like any other product.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import select

from app.constants.product_categories import PRODUCT_CATEGORY_BY_SLUG
from app.db.session import SessionLocal
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PEN_FORM = "pen"
# Bare mg number(s): "1.5", "10", "10/10/50". The web/API strength
# formatters append "mg" only to values of this shape.
SIZE_KEY_RE = re.compile(r"^[\d.]+(/[\d.]+)*$")
# Real supplier ids observed so far are 8-digit; this range can never
# collide with a synced id.
_PLACEHOLDER_ID_BASE = 900_000_000
_PENS_SUPPLIER_KEY = "umsrx"  # the pens/pre-constituted supplier account


@dataclass(frozen=True)
class PenSize:
    size_key: str  # mg per 3 mL pen: "1.5", "10/10/50"
    price_cents: int  # suggested retail, integer cents
    sheet_name: str  # the price sheet's row name — fulfillment-only


@dataclass(frozen=True)
class PenProduct:
    slug: str
    name: str
    sizes: tuple[PenSize, ...]
    # "/products/pens/<slug>-<size>.<ext>" in ascending size order; empty
    # means the storefront renders its letter-tile placeholder.
    images: tuple[str, ...] = ()
    description: str = "Pre-filled 3 mL auto-injector pen."
    content: dict = field(default_factory=dict)


def variant_sku(slug: str, size_key: str) -> str:
    return f"TC-{slug.upper()}-PEN-{size_key.upper().replace('/', '-')}"[:100]


def variant_name(product_name: str, size_key: str) -> str:
    return f"{product_name} {size_key}mg pen"


def _single(slug: str, name: str, size_key: str, price_cents: int, image: str | None = None) -> PenProduct:
    return PenProduct(
        slug=slug,
        name=name,
        sizes=(PenSize(size_key, price_cents, name if "(" not in name else name.split(" (")[0]),),
        images=(f"/products/pens/{image}",) if image else (),
    )


_PENS: tuple[PenProduct, ...] = (
    # TODO(attorney-review): GLP-class display names carry the drug name in
    # parentheses (David, 2026-09-05). Slugs stay code names so
    # lib/compliance.ts keeps them off every promotional surface.
    PenProduct(
        slug="glp-1s",
        name="GLP-1S (Semaglutide)",
        sizes=(
            PenSize("1.5", 25900, "Semaglutide Month 1"),
            PenSize("3.5", 28900, "Semaglutide Month 2"),
            PenSize("5.5", 30900, "Semaglutide Month 3"),
            PenSize("7.5", 33900, "Semaglutide Month 4"),
            PenSize("10", 35900, "Semaglutide Month 5"),
        ),
        images=tuple(f"/products/pens/glp-1s-{s}" for s in ("1.5.png", "3.5.png", "5.5.png", "7.5.png", "10.jpg")),
    ),
    PenProduct(
        slug="glp-2t",
        name="GLP-2T (Tirzepatide)",
        sizes=(
            PenSize("10", 33900, "Tirzepatide Month 1"),
            PenSize("20", 37900, "Tirzepatide Month 2"),
            PenSize("30", 39900, "Tirzepatide Month 3"),
            PenSize("40", 42900, "Tirzepatide Month 4"),
            PenSize("50", 45900, "Tirzepatide Month 5"),
            PenSize("60", 48900, "Tirzepatide Month 6"),
        ),
        images=tuple(f"/products/pens/glp-2t-{s}.jpg" for s in ("10", "20", "30", "40", "50", "60")),
    ),
    PenProduct(
        slug="glp-3r",
        name="GLP-3R (Retatrutide)",
        sizes=(
            PenSize("8", 23900, "Reta Month 1"),
            PenSize("16", 28900, "Reta Month 2"),
            PenSize("24", 33900, "Reta Month 3"),
            PenSize("32", 37900, "Reta Month 4"),
            PenSize("40", 42900, "Reta Month 5"),
            PenSize("48", 46900, "Reta Month 6"),
        ),
        images=tuple(f"/products/pens/glp-3r-{s}" for s in ("8.jpg", "16.jpg", "24.jpg", "32.jpg", "40.jpg", "48.png")),
    ),
    _single("tesamorelin", "Tesamorelin", "30", 20900, "tesamorelin-30.jpg"),
    _single("sermorelin", "Sermorelin", "10", 13900, "sermorelin-10.jpg"),
    _single("ipamorelin", "Ipamorelin", "10", 12900, "ipamorelin-10.jpg"),
    _single("tesamorelin-ipamorelin", "Tesamorelin / Ipamorelin", "12/3", 22900, "tesamorelin-ipamorelin-12-3.png"),
    _single("glow-bpc-157-tb-500-ghk", "GLOW (BPC-157 / TB-500 / GHK-Cu)", "10/10/50", 18900, "glow-bpc-157-tb-500-ghk-10-10-50.jpg"),
    _single("klow-kpv-bpc-157-tb-500-ghk", "KLOW (KPV / BPC-157 / TB-500 / GHK-Cu)", "10/10/10/50", 21900, "klow-kpv-bpc-157-tb-500-ghk-10-10-10-50.jpg"),
    _single("cjc-1295-no-dac", "CJC-1295 (no DAC)", "10", 11900, "cjc-1295-no-dac-10.jpg"),
    _single("cjc-no-dac-ipamorelin", "CJC-1295 (no DAC) / Ipamorelin", "10/10", 22900, "cjc-no-dac-ipamorelin-10-10.jpg"),
    PenProduct(
        slug="bpc-157",
        name="BPC-157",
        sizes=(PenSize("10", 10900, "BPC-157 10mg"), PenSize("20", 14900, "BPC-157 20mg")),
        # Only the 20 mg pen has a render; it stands in for the product tile.
        images=("/products/pens/bpc-157-20.jpg",),
    ),
    _single("tb-500", "TB-500", "10", 15900, "tb-500-10.jpg"),
    _single("bpc-157-tb-500-wolverine", "BPC-157 / TB-500 (Wolverine)", "10/10", 21900, "bpc-157-tb-500-wolverine-10-10.jpg"),
    _single("hcg-6000-units", "HCG (6000 units)", "3", 20900, "hcg-6000-units-3.jpg"),
    _single("nad", "NAD+", "500", 20900, "nad-500.png"),
    _single("pt-141", "PT-141", "10", 10900, "pt-141-10.jpg"),
    _single("igf1-lr3", "IGF-1 LR3", "1", 20900, "igf1-lr3-1.png"),
    PenProduct(
        slug="mots-c",
        name="MOTS-C",
        sizes=(PenSize("10", 10900, "MOTS-C 10mg"), PenSize("20", 14900, "MOTS-C 20mg"), PenSize("40", 22900, "MOTS-C 40mg")),
        images=("/products/pens/mots-c-10.jpg", "/products/pens/mots-c-20.jpg", "/products/pens/mots-c-40.png"),
    ),
    # TODO(attorney-review): see the GLP note above.
    _single("cagrilinitide", "Cagrilinitide (Cagrilintide)", "10", 23900, "cagrilinitide-10.png"),
    _single("ghk-cu", "GHK-Cu", "50", 9900, "ghk-cu-50.jpg"),
    _single("hexarelin", "Hexarelin", "5", 16900, "hexarelin-5.jpg"),
    _single("ta-1", "TA-1", "10", 18900, "ta-1-10.png"),
    _single("epithalon", "Epithalon", "60", 32900, "epithalon-60.png"),
    _single("kisspeptin", "Kisspeptin", "5", 18900, "kisspeptin-5.png"),
    _single("kpv", "KPV", "10", 11900, "kpv-10.png"),
    _single("ll-37", "LL-37", "10", 16900, "ll-37-10.png"),
    _single("selank", "Selank", "20", 14900, "selank-20.png"),
    _single("semax", "Semax", "20", 14900, "semax-20.png"),
    _single("ss-31", "SS-31", "50", 36900, "ss-31-50.png"),
    _single("dsip", "DSIP", "5", 9900, "dsip-5.jpg"),
    _single("dihexa", "Dihexa", "10", 9900, "dihexa-10.png"),
    _single("glutathione", "Glutathione", "600", 11900, "glutathione-600.png"),
    _single("5-amino-1mq", "5-Amino-1MQ", "50", 7900, "5-amino-1mq-50.png"),
)


def _next_placeholder_id(session) -> int:
    current = session.execute(
        select(SupplierProduct.supplier_product_id)
        .where(SupplierProduct.supplier_product_id >= _PLACEHOLDER_ID_BASE)
        .order_by(SupplierProduct.supplier_product_id.desc())
        .limit(1)
    ).scalar_one_or_none()
    return (current or _PLACEHOLDER_ID_BASE) + 1


def _activate(session, variant: ProductVariant, sheet_name: str) -> None:
    """Give the variant a placeholder MAPPED mapping (if it has none) and
    set is_sellable through the validator."""
    has_mapping = any(m.mapping_status == "MAPPED" and m.is_active for m in variant.supplier_mappings)
    if not has_mapping:
        supplier_product = SupplierProduct(
            supplier_product_id=_next_placeholder_id(session),
            supplier_key=_PENS_SUPPLIER_KEY,
            supplier_sku=f"PENDING-{variant.sku}",
            supplier_name=sheet_name,
            supplier_active=True,
            raw_payload={"placeholder": True, "reason": "seed_pen_catalog", "sheet_name": sheet_name},
        )
        session.add(supplier_product)
        session.flush()
        session.add(
            SupplierProductMapping(
                product_variant_id=variant.id,
                supplier_product_id=supplier_product.supplier_product_id,
                supplier_key=_PENS_SUPPLIER_KEY,
                supplier_sku=supplier_product.supplier_sku,
                supplier_name=supplier_product.supplier_name,
                mapping_status="MAPPED",
                match_confidence="MANUAL",
            )
        )
        session.flush()
        session.refresh(variant)
    variant.is_sellable = True


def seed_pen_catalog(session=None) -> dict[str, int]:
    owns_session = session is None
    session = session or SessionLocal()
    counts = {"products_created": 0, "variants_created": 0, "activated": 0, "hidden": 0}
    try:
        seeded_skus: set[str] = set()
        for pen in _PENS:
            product = session.execute(select(Product).where(Product.slug == pen.slug)).scalar_one_or_none()
            if product is None:
                product = Product(slug=pen.slug, name=pen.name, images=[], is_active=True)
                session.add(product)
                counts["products_created"] += 1
            product.name = pen.name
            product.description = pen.description
            product.content = dict(pen.content)
            product.images = list(pen.images)
            product.category = PRODUCT_CATEGORY_BY_SLUG[pen.slug]
            product.is_active = True
            session.flush()

            for size in pen.sizes:
                sku = variant_sku(pen.slug, size.size_key)
                seeded_skus.add(sku)
                variant = session.execute(select(ProductVariant).where(ProductVariant.sku == sku)).scalar_one_or_none()
                if variant is None:
                    variant = ProductVariant(
                        product_id=product.id,
                        sku=sku,
                        name=variant_name(pen.name, size.size_key),
                        retail_price_cents=size.price_cents,
                        size_key=size.size_key,
                        form=PEN_FORM,
                    )
                    session.add(variant)
                    session.flush()
                    counts["variants_created"] += 1
                variant.product_id = product.id
                variant.name = variant_name(pen.name, size.size_key)
                variant.retail_price_cents = size.price_cents
                variant.size_key = size.size_key
                variant.form = PEN_FORM
                if not variant.is_sellable:
                    _activate(session, variant, size.sheet_name)
                    counts["activated"] += 1
            session.flush()

        strays = session.execute(
            select(ProductVariant).where(ProductVariant.is_sellable.is_(True), ProductVariant.sku.not_in(seeded_skus))
        ).scalars()
        for variant in strays:
            variant.is_sellable = False
            counts["hidden"] += 1

        session.commit()
        logger.info("seed_pen_catalog: %s", counts)
        return counts
    finally:
        if owns_session:
            session.close()


if __name__ == "__main__":
    seed_pen_catalog()
