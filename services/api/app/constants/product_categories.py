"""Source of truth for Product.category across the combined catalog (pens
and lyophilized vials).

Product.category is a free String(100) column with no DB enum or CHECK
constraint (see catalog.py), so nothing stops a bad value being written.
This module is the value set everything else agrees on.

The taxonomy is INTERNAL ONLY. Nothing on the storefront renders it (the
customer-facing benefit groups are apps/web/src/lib/categories.ts, a
separate presentation-layer list). It exists for the admin CSV, the
/shop/filter-options endpoint and future internal reporting.

Combined site (2026-10-22): the union of the pens site's mapping and the
vial site's. Where the two disagreed (kisspeptin, igf1-lr3) the pens
site's newer placement wins; the six vial-only slugs (aod-9604, ghrp-2,
ghrp-6, ghk-cu-kpv, mt-1, bac-water) keep the vial site's.

Consumers:

- app.scripts.seed_pen_catalog and app.scripts.seed_lyo_catalog stamp
  PRODUCT_CATEGORY_BY_SLUG onto every product they create or refresh.
  Every slug in either seed table must be present here
  (tests/test_seed_pen_catalog.py and tests/test_seed_lyo_catalog.py
  enforce it).
- alembic revision d4e5f6a7b8c9 (inherited from the vial site) embeds a
  frozen copy of the vial-era mapping; it is a no-op on this site's
  fresh database and must not be edited.
"""

LAUNCH_CATEGORIES: list[str] = [
    "GLP-1 & Metabolic",
    "Growth Hormone & Recovery",
    "Healing & Repair Blends",
    "Longevity & Cognitive",
    "Sexual Health & Hormonal",
    "Supplies",
]

# All 35 pen products (52 pens) from David's 2026-09-05 pen price sheet,
# plus the six vial-only products from the 9.1.26 lyophilized ladder.
PRODUCT_CATEGORY_BY_SLUG: dict[str, str] = {
    "glp-1s": "GLP-1 & Metabolic",
    "glp-2t": "GLP-1 & Metabolic",
    "glp-3r": "GLP-1 & Metabolic",
    "cagrilinitide": "GLP-1 & Metabolic",
    "5-amino-1mq": "GLP-1 & Metabolic",
    "aod-9604": "GLP-1 & Metabolic",
    "tesamorelin": "Growth Hormone & Recovery",
    "sermorelin": "Growth Hormone & Recovery",
    "ipamorelin": "Growth Hormone & Recovery",
    "tesamorelin-ipamorelin": "Growth Hormone & Recovery",
    "cjc-1295-no-dac": "Growth Hormone & Recovery",
    "cjc-no-dac-ipamorelin": "Growth Hormone & Recovery",
    "hexarelin": "Growth Hormone & Recovery",
    "mots-c": "Growth Hormone & Recovery",
    "igf1-lr3": "Growth Hormone & Recovery",
    "ghrp-2": "Growth Hormone & Recovery",
    "ghrp-6": "Growth Hormone & Recovery",
    "bpc-157": "Healing & Repair Blends",
    "tb-500": "Healing & Repair Blends",
    "bpc-157-tb-500-wolverine": "Healing & Repair Blends",
    "glow-bpc-157-tb-500-ghk": "Healing & Repair Blends",
    "klow-kpv-bpc-157-tb-500-ghk": "Healing & Repair Blends",
    "kpv": "Healing & Repair Blends",
    "ghk-cu": "Healing & Repair Blends",
    "ll-37": "Healing & Repair Blends",
    "ghk-cu-kpv": "Healing & Repair Blends",
    "nad": "Longevity & Cognitive",
    "epithalon": "Longevity & Cognitive",
    "ss-31": "Longevity & Cognitive",
    "ta-1": "Longevity & Cognitive",
    "dsip": "Longevity & Cognitive",
    "selank": "Longevity & Cognitive",
    "semax": "Longevity & Cognitive",
    "dihexa": "Longevity & Cognitive",
    "glutathione": "Longevity & Cognitive",
    "kisspeptin": "Sexual Health & Hormonal",
    "pt-141": "Sexual Health & Hormonal",
    "mt-2": "Sexual Health & Hormonal",
    "hcg-6000-units": "Sexual Health & Hormonal",
    "mt-1": "Sexual Health & Hormonal",
    # Bacteriostatic water is a reconstitution supply, not a research
    # compound; it has no customer-facing benefit group.
    "bac-water": "Supplies",
}
