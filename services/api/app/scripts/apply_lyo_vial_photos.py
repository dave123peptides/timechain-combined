"""Manual entrypoint: python -m app.scripts.apply_lyo_vial_photos

David added real product photography for the lyophilized vials to
apps/web/public/LYO Vials 8-24/ on 2026-08-24 (copied into
public/products/ as <slug>-lyo.png). This replaces the placeholder/stock
images on those products' `images` field with the real photo.

PT-141 and SS-31 were added to the same folder in a later batch the same
day, once David had real vial photos for those two as well. GLP-1S,
GLP-2T, and GLP-3R followed in a third batch, also 2026-08-24.

Idempotent — safe to rerun.
"""

import logging

from app.db.session import SessionLocal
from app.models.catalog import Product

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# slug -> new sole image path
_LYO_PHOTOS: dict[str, str] = {
    "aod-9604": "/products/aod-9604-lyo.png",
    "epithalon": "/products/epithalon-lyo.png",
    "ghk-cu-kpv": "/products/ghk-cu-kpv-lyo.png",
    "ghrp-2": "/products/ghrp-2-lyo.png",
    "ghrp-6": "/products/ghrp-6-lyo.png",
    "hcg-6000-units": "/products/hcg-6000-units-lyo.png",
    "kisspeptin": "/products/kisspeptin-lyo.png",
    "mots-c": "/products/mots-c-lyo.png",
    "nad": "/products/nad-lyo.png",
    "sermorelin": "/products/sermorelin-lyo.png",
    "tb-500": "/products/tb-500-lyo.png",
    "tesamorelin-ipamorelin": "/products/tesamorelin-ipamorelin-lyo.png",
    "tesamorelin": "/products/tesamorelin-lyo.png",
    "pt-141": "/products/pt-141-lyo.png",
    "ss-31": "/products/ss-31-lyo.png",
    "glp-1s": "/products/glp-1s-lyo.png",
    "glp-2t": "/products/glp-2t-lyo.png",
    "glp-3r": "/products/glp-3r-lyo.png",
}


def apply_lyo_vial_photos() -> None:
    session = SessionLocal()
    try:
        updated = 0
        products = session.query(Product).filter(Product.slug.in_(_LYO_PHOTOS)).all()
        found_slugs = {p.slug for p in products}
        missing = _LYO_PHOTOS.keys() - found_slugs
        if missing:
            logger.warning("apply_lyo_vial_photos: no product row for slugs=%s", sorted(missing))

        for product in products:
            new_image = _LYO_PHOTOS[product.slug]
            if product.images != [new_image]:
                product.images = [new_image]
                updated += 1

        session.commit()
        logger.info("apply_lyo_vial_photos: updated=%d products", updated)
    finally:
        session.close()


if __name__ == "__main__":
    apply_lyo_vial_photos()
