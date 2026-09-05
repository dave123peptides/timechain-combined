"""Manual entrypoint: python -m app.scripts.sync_lyo_catalog

David's 2026-08-22 decision: TimeChain sells lyophilized vials only — no
pens, no preconstituted/finished-good vials, no rx vials. This script
brings the catalog in line with that and with the "TimeChain RUO LYO -
Final Pricing 9.1.26" sheet (v3 8.22.26 ladder + targeted corrections):

1. Every product NOT in _LADDER gets every variant hidden
   (is_sellable=False) — it's off the curated LYO lineup entirely.
2. Every product IN _LADDER: any non-lyophilized-form variant (vial,
   preconstituted, pen, rx_vial) gets hidden too — only the lyophilized
   SKU should ever be sellable for these.
3. Each lyophilized variant matching a (slug, size_key) in _LADDER gets
   its retail_price_cents updated to the new ladder price.

Deliberately never touches is_sellable=True — that stays exactly as the
existing supplier-mapping validation already set it (see
ProductVariant._validate_is_sellable). Several ladder items don't have a
verified lyophilized supplier match yet (only pen-form candidates exist
in the current AllianceTek feed, per /admin/products); those stay
whatever they already are, not forced live. David's call (2026-08-23):
handle that sourcing gap separately via admin approval, not by this
script.

4. Each ladder product's category is normalized to the merchandising
   taxonomy in app.constants.product_categories. That mapping used to be
   a private _CATEGORY dict here; it moved out so this script and alembic
   revision d4e5f6a7b8c9 (which applied the same taxonomy to the existing
   rows) cannot drift apart. Re-running this after a catalog re-import
   re-normalizes any freshly created rows.

Idempotent — safe to rerun after editing _LADDER or re-running catalog
import.
"""

import logging

from app.constants.product_categories import PRODUCT_CATEGORY_BY_SLUG
from app.db.session import SessionLocal
from app.models.catalog import Product, ProductVariant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# slug -> {size_key: retail_price_cents}, from the Final Pricing 9.1.26 sheet.
_LADDER: dict[str, dict[str, int]] = {
    "glp-1s": {"10": 11900, "20": 15900, "50": 34900},
    "glp-2t": {"10": 9900, "30": 20900, "60": 34900, "100": 50900},
    "glp-3r": {"10": 13900, "20": 19900, "30": 25900, "60": 44900, "100": 64900},
    "tesamorelin": {"10": 9900, "32": 19900},
    "sermorelin": {"10": 8900},
    "ipamorelin": {"10": 7900},
    "tesamorelin-ipamorelin": {"10/10": 11900},
    "glow-bpc-157-tb-500-ghk": {"10/10/50": 14900},
    "klow-kpv-bpc-157-tb-500-ghk": {"10/10/10/50": 19900},
    "cjc-no-dac-ipamorelin": {"10/10": 9900},
    "bpc-157": {"10": 8900, "20": 9900},
    "tb-500": {"10": 11900},
    "bpc-157-tb-500-wolverine": {"10/10": 12900},
    "hcg-6000-units": {"3": 7900},
    "aod-9604": {"5": 6900},
    "nad": {"500": 11900, "1000": 14900},
    "pt-141": {"10": 5500},
    "igf1-lr3": {"1": 11900},
    "mots-c": {"10": 9900, "20": 14900},
    "mt-1": {"10": 5500},
    "mt-2": {"10": 5500},
    "cagrilinitide": {"10": 12900},
    "ghk-cu": {"50": 5900},
    "ghk-cu-kpv": {"50/10": 7900},
    "ghrp-2": {"10": 5200},
    "ghrp-6": {"10": 5200},
    "ta-1": {"10": 12900},
    "epithalon": {"50": 15900},
    "kisspeptin": {"5": 4900},
    "kpv": {"10": 7900},
    "selank": {"10": 6900},
    "semax": {"10": 6900},
    "ss-31": {"50": 16500},
    "dsip": {"5": 5500},
    # $10 per David 9/2 — BAC water sells via the PDP reconstitution
    # addon now, not the catalog grid (a storefront-only distinction).
    "bac-water": {"10mL": 1000},
}

# Reused as a placeholder photo on ladder products with no real photo of
# their own yet — see ProductImagePlaceholder.tsx's comment for why this
# is temporary, not a substitute for real per-product photography.
_PLACEHOLDER_IMAGE = "/products/bpc-157-1.jpg"


def sync_lyo_catalog() -> None:
    session = SessionLocal()
    try:
        products = list(session.query(Product).all())
        hidden = 0
        priced = 0
        placeholdered = 0

        for product in products:
            ladder_sizes = _LADDER.get(product.slug)

            if ladder_sizes is None:
                for variant in product.variants:
                    if variant.is_sellable:
                        variant.is_sellable = False
                        hidden += 1
                continue

            if not product.images:
                product.images = [_PLACEHOLDER_IMAGE]
                placeholdered += 1

            category = PRODUCT_CATEGORY_BY_SLUG.get(product.slug)
            if category is not None and product.category != category:
                product.category = category

            for variant in product.variants:
                if variant.form != "lyophilized":
                    if variant.is_sellable:
                        variant.is_sellable = False
                        hidden += 1
                    continue

                new_price = ladder_sizes.get(variant.size_key or "")
                if new_price is not None and variant.retail_price_cents != new_price:
                    variant.retail_price_cents = new_price
                    priced += 1

        session.commit()
        logger.info(
            "sync_lyo_catalog: hidden=%d non-ladder/non-lyo variants, "
            "priced=%d lyophilized variants updated, placeholdered=%d products",
            hidden,
            priced,
            placeholdered,
        )
    finally:
        session.close()


if __name__ == "__main__":
    sync_lyo_catalog()
