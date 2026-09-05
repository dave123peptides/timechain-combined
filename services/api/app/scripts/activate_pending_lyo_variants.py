"""Manual entrypoint: python -m app.scripts.activate_pending_lyo_variants

David's call (2026-08-23): get the full 35-item LYO ladder live and
purchasable on the site now; real AllianceTek supplier SKU matching for
the variants that don't have a genuine lyophilized match yet gets sorted
out later, separately.

For every _LADDER_VARIANTS entry whose variant isn't already sellable,
this creates an obviously-fake placeholder SupplierProduct + a MANUAL
SupplierProductMapping (never a real supplier identity — supplier_sku
starts with "PENDING-", supplier_product_id is out of AllianceTek's real
id range) and flips is_sellable True through that mapping, so it goes
through ProductVariant._validate_is_sellable for real rather than
bypassing it.

IMPORTANT — self-expiring by design, not a bug: because these
supplier_product_ids are fake, the next time a *real* supplier catalog
sync runs (services/worker/worker/supplier_sync), reconciliation will
see each one as "disappeared from the feed" and automatically flip
is_sellable back to False (see reconciliation.py's
reconcile_mapping_drift — that's the intended safety behavior, not a
regression). No scheduled sync runs in local dev today, so that won't
happen here, but it will the moment a real sync is wired up — at which
point each of these needs its real supplier_sku from David and a proper
admin approval via /admin/products, same as any other product.

Idempotent — rerunning skips variants that are already sellable
(including ones already activated by a prior run of this script).
"""

import logging

from app.db.session import SessionLocal
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Same (slug, size_key) universe as app.scripts.sync_lyo_catalog._LADDER —
# every product/size TimeChain intends to sell as a lyophilized vial.
_LADDER_VARIANTS: list[tuple[str, str]] = [
    ("glp-1s", "10"), ("glp-1s", "20"), ("glp-1s", "50"),
    ("glp-2t", "10"), ("glp-2t", "30"), ("glp-2t", "60"), ("glp-2t", "100"),
    ("glp-3r", "10"), ("glp-3r", "20"), ("glp-3r", "30"), ("glp-3r", "60"), ("glp-3r", "100"),
    ("tesamorelin", "10"), ("tesamorelin", "32"),
    ("sermorelin", "10"),
    ("ipamorelin", "10"),
    ("tesamorelin-ipamorelin", "10/10"),
    ("glow-bpc-157-tb-500-ghk", "10/10/50"),
    ("klow-kpv-bpc-157-tb-500-ghk", "10/10/10/50"),
    ("cjc-no-dac-ipamorelin", "10/10"),
    ("bpc-157", "10"), ("bpc-157", "20"),
    ("tb-500", "10"),
    ("bpc-157-tb-500-wolverine", "10/10"),
    ("hcg-6000-units", "3"),
    ("aod-9604", "5"),
    ("nad", "500"), ("nad", "1000"),
    ("pt-141", "10"),
    ("igf1-lr3", "1"),
    ("mots-c", "10"), ("mots-c", "20"),
    ("mt-1", "10"),
    ("mt-2", "10"),
    ("cagrilinitide", "10"),
    ("ghk-cu", "50"),
    ("ghk-cu-kpv", "50/10"),
    ("ghrp-2", "10"),
    ("ghrp-6", "10"),
    ("ta-1", "10"),
    ("epithalon", "50"),
    ("kisspeptin", "5"),
    ("kpv", "10"),
    ("selank", "10"),
    ("semax", "10"),
    ("ss-31", "50"),
    ("dsip", "5"),
    ("bac-water", "10mL"),
]

# Real AllianceTek ids observed so far are 8-digit (26xxxxxx / 29xxxxxx) —
# this range can never collide with a real synced id.
_PLACEHOLDER_ID_BASE = 900_000_000


def activate_pending_lyo_variants() -> None:
    session = SessionLocal()
    try:
        next_placeholder_id = _PLACEHOLDER_ID_BASE + (
            session.query(SupplierProduct)
            .filter(SupplierProduct.supplier_product_id >= _PLACEHOLDER_ID_BASE)
            .count()
        )

        activated = 0
        already_sellable = 0
        not_found = 0

        for slug, size_key in _LADDER_VARIANTS:
            product = session.query(Product).filter(Product.slug == slug).one_or_none()
            if product is None:
                not_found += 1
                logger.warning("no product for slug=%r", slug)
                continue

            variant = next(
                (v for v in product.variants if v.form == "lyophilized" and v.size_key == size_key), None
            )
            if variant is None:
                not_found += 1
                logger.warning("no lyophilized %r variant for slug=%r", size_key, slug)
                continue

            if variant.is_sellable:
                already_sellable += 1
                continue

            next_placeholder_id += 1
            supplier_product = SupplierProduct(
                supplier_product_id=next_placeholder_id,
                supplier_sku=f"PENDING-{variant.sku}",
                supplier_name=f"PENDING REAL SUPPLIER MATCH — {variant.name}",
                supplier_active=True,
                raw_payload={"placeholder": True, "reason": "activate_pending_lyo_variants"},
            )
            session.add(supplier_product)
            session.flush()

            mapping = SupplierProductMapping(
                product_variant_id=variant.id,
                supplier_product_id=supplier_product.supplier_product_id,
                supplier_sku=supplier_product.supplier_sku,
                supplier_name=supplier_product.supplier_name,
                mapping_status="MAPPED",
                match_confidence="MANUAL",
            )
            session.add(mapping)
            session.flush()

            variant.is_sellable = True
            activated += 1

        session.commit()
        logger.info(
            "activate_pending_lyo_variants: activated=%d, already_sellable=%d, not_found=%d",
            activated,
            already_sellable,
            not_found,
        )
    finally:
        session.close()


if __name__ == "__main__":
    activate_pending_lyo_variants()
