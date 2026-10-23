"""Manual entrypoint: python -m app.scripts.seed_pen_catalog

The pen catalog's source of truth. `_PENS` below is David's 2026-09-05
pen price sheet, one entry per product, one `PenSize` per purchasable pen.

Combined site (2026-10-22): this storefront sells pens AND lyophilized
vials, one product row per compound. This script owns the pen side of
every product: the pen variants, the pen renders at the front of
`Product.images`, and (because David's TCP Guide copy is the newer brand
voice) the product's name, tagline and About overview. The vial side is
app.scripts.seed_lyo_catalog, which adds lyophilized variants to the same
rows and fills in the structured copy this script leaves empty. Each
script hides only stray variants of ITS OWN form, and merges rather than
replaces `images`/`content`, so the two can run in either order and as
often as needed.

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
- sets is_sellable=False on any PEN variant whose SKU is not in the table
  (lyophilized variants belong to seed_lyo_catalog and are left alone).

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
from dataclasses import dataclass, field, replace

from sqlalchemy import select

from app.constants.product_categories import PRODUCT_CATEGORY_BY_SLUG
from app.db.session import SessionLocal
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PEN_FORM = "pen"
# The tagline a pen gets when the TCP Guide has no copy for it.
GENERIC_PEN_DESCRIPTION = "Pre-filled 3 mL auto-injector pen."
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
    description: str = GENERIC_PEN_DESCRIPTION
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


# Per-pen copy from David's TCP Guide (https://tcpguidehelp.vercel.app/),
# slug -> (chemistry subtitle, description), verbatim (David, 2026-09-05).
# The subtitle becomes the tagline under the product name unless the name
# already carries it (the GLP code names); the description becomes the
# About tab's overview. Pens the guide doesn't cover keep the generic
# tagline and no About tab.
#
# TODO(attorney-review): these are the guide's benefit-framed sentences
# (weight loss, arousal, muscle growth) — human-outcome language the vial
# site's standing rules exclude. David chose to show them on this site.
_GUIDE: dict[str, tuple[str, str]] = {
    "glp-1s": ("Semaglutide", "Strong appetite suppression and significant weight loss, with improved blood sugar control and added cardiovascular benefits."),
    "glp-2t": ("Tirzepatide", "A dual GLP-1/GIP agonist that delivers superior weight loss and glycemic control compared to pure GLP-1s."),
    "glp-3r": ("Retatrutide", "A triple agonist hitting GLP-1, GIP, and glucagon at once — currently one of the most potent options available for fat loss and overall metabolic improvement."),
    "cagrilinitide": ("Amylin analog", "Reduces appetite and slows gastric emptying through a separate pathway from GLP-1s, which is why it's often stacked with them for enhanced weight loss."),
    "mots-c": ("Mitochondrial-derived peptide", "Improves insulin sensitivity, exercise capacity, fat metabolism, and overall metabolic flexibility — often described as an exercise mimetic."),
    "5-amino-1mq": ("NNMT inhibitor", "Boosts NAD+ levels, increases energy expenditure, and supports fat loss while helping preserve lean muscle mass."),
    "bpc-157": ("Body Protection Compound-157", "Accelerates healing of tendons, ligaments, muscles, and gut lining. Strongly anti-inflammatory, with well-known gut repair benefits."),
    "tb-500": ("Thymosin Beta-4 fragment", "Promotes cell migration and flexibility, speeding recovery from soft-tissue injuries while reducing inflammation."),
    "bpc-157-tb-500-wolverine": ("BPC-157 / TB-500 blend", "The synergistic healing stack — faster recovery from injuries, joint issues, and soft-tissue damage than either compound alone."),
    "ghk-cu": ("Copper peptide", "Wound healing, skin repair, and collagen production, plus anti-inflammatory action and support for hair and tissue regeneration."),
    "glow-bpc-157-tb-500-ghk": ("BPC-157 / TB-500 / GHK-Cu blend", "Full-spectrum recovery paired with skin and anti-aging support — healing and aesthetics in a single blend."),
    "klow-kpv-bpc-157-tb-500-ghk": ("KPV / BPC-157 / TB-500 / GHK-Cu blend", "Everything GLOW offers, plus added anti-inflammatory gut support from KPV — the most complete repair blend in the lineup."),
    "kpv": ("Lysine-Proline-Valine", "A potent anti-inflammatory, especially for the gut and skin. Supports barrier function and helps balance immune response."),
    "cjc-no-dac-ipamorelin": ("No DAC — GHRH + GHRP blend", "The gold-standard synergistic GH stack — CJC raises GH pulse amplitude and frequency while Ipamorelin adds a clean release, together supporting fat loss, recovery, and deeper sleep."),
    "ipamorelin": ("Selective GHRP", "Clean GH release with minimal side effects — no meaningful spike in hunger, cortisol, or prolactin."),
    "tesamorelin": ("GHRH analog", "A potent GHRH analog best known for specifically reducing visceral belly fat and improving overall body composition."),
    "tesamorelin-ipamorelin": ("Dual secretagogue blend", "Enhanced GH release combined with targeted visceral fat reduction — the stronger option for body recomposition."),
    "sermorelin": ("GHRH analog", "The classic GHRH analog — milder and more physiological GH stimulation, a gentler entry point than Tesamorelin."),
    "igf1-lr3": ("Long R3 IGF-1", "A long-acting IGF-1 analog for muscle growth, recovery, and nutrient partitioning."),
    "selank": ("Tuftsin analog", "An anxiolytic that improves mood, focus, and stress resilience, with mild nootropic effects and no sedation or dependence."),
    "semax": ("ACTH(4-10) analog", "Neuroprotective and cognition-enhancing — sharpens focus and memory while raising BDNF. Widely used for cognitive performance."),
    "dihexa": ("Angiotensin IV analog", "Drives formation of new brain synapses — studied for restoring memory and learning, and for recovery of cognitive function after injury."),
    "dsip": ("Delta Sleep-Inducing Peptide", "Promotes deeper, more restorative sleep and may help with stress regulation and overall recovery."),
    "epithalon": ("Epithalamin fragment", "Telomere support, circadian rhythm regulation, and anti-aging effects working through the pineal gland."),
    "mt-2": ("Melanotan II", "Tanning plus a significant libido boost, with appetite suppression as an added effect."),
    "pt-141": ("Bremelanotide", "Increases sexual desire and arousal in both men and women, working through melanocortin receptors in the brain rather than blood flow."),
    "kisspeptin": ("GPR54 (KISS1R) agonist", "Stimulates GnRH, which drives LH and FSH release — supporting the reproductive hormone axis, natural testosterone, and fertility signaling."),
    "nad": ("Nicotinamide Adenine Dinucleotide", "Boosts cellular energy (ATP), DNA repair, and sirtuin activation — the central compound for longevity pathways and restored mental clarity."),
    "ss-31": ("Elamipretide", "A mitochondrial membrane stabilizer that improves energy production and reduces oxidative stress in aging or damaged cells."),
    "glutathione": ("Master antioxidant", "The body's master antioxidant — supports detoxification, immune function, and skin brightening while reducing oxidative stress."),
    "ta-1": ("Thymosin Alpha-1", "A potent immune modulator that enhances T-cell function — used for immune support and studied heavily for antiviral response."),
    "ll-37": ("Cathelicidin host-defense peptide", "An antimicrobial defense peptide that targets resistant bacteria, fungi, and biofilms while recruiting immune cells to the site."),
}


def _with_guide(pen: PenProduct) -> PenProduct:
    entry = _GUIDE.get(pen.slug)
    if entry is None:
        return pen
    subtitle, description = entry
    tagline = pen.description if subtitle.lower() in pen.name.lower() else subtitle
    return replace(pen, description=tagline, content={**pen.content, "overview": description})

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
    # Added by David on 2026-09-05 (not on the original sheet): MT-II 10 mg, $140.
    _single("mt-2", "MT-II", "10", 14000, "mt-2-10.png"),
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
_PENS = tuple(_with_guide(pen) for pen in _PENS)


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
            # The guide's chemistry subtitle always wins; the generic pen
            # tagline only fills an empty row, so a compound that also
            # ships as a vial keeps the vial site's tagline (seed_lyo_catalog).
            if pen.description != GENERIC_PEN_DESCRIPTION or not product.description:
                product.description = pen.description
            # Merge, don't replace: seed_lyo_catalog fills key_points /
            # research_areas / pairs_with / faq on the same row. The pen
            # overview wins where both have one.
            product.content = {**(product.content or {}), **pen.content}
            # Pen renders lead; any other seed's photos (the lyophilized
            # vial shot) follow so the gallery shows both forms.
            product.images = list(pen.images) + [
                image for image in (product.images or []) if not image.startswith("/products/pens/")
            ]
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
            select(ProductVariant).where(
                ProductVariant.is_sellable.is_(True),
                ProductVariant.form == PEN_FORM,
                ProductVariant.sku.not_in(seeded_skus),
            )
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
