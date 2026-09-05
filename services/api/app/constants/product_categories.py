"""Source of truth for Product.category across the pen catalog.

Product.category is a free String(100) column with no DB enum or CHECK
constraint (see catalog.py), so nothing stops a bad value being written.
This module is the value set everything else agrees on.

The taxonomy is INTERNAL ONLY. Nothing on the storefront renders a
category (benefit-named groups like "GLP-1 & Metabolic" read as
intended-use claims, incompatible with the RUO positioning — see
apps/web/src/app/(storefront)/shop/page.tsx). It exists for the admin
CSV, the /shop/filter-options endpoint and future internal reporting.

Consumers:

- app.scripts.seed_pen_catalog stamps PRODUCT_CATEGORY_BY_SLUG onto every
  product it creates or refreshes. Every slug in the seed table must be
  present here (tests/test_seed_pen_catalog.py enforces it).
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
]

# All 35 pen products (52 pens) from David's 2026-09-05 pen price sheet.
PRODUCT_CATEGORY_BY_SLUG: dict[str, str] = {
    "glp-1s": "GLP-1 & Metabolic",
    "glp-2t": "GLP-1 & Metabolic",
    "glp-3r": "GLP-1 & Metabolic",
    "cagrilinitide": "GLP-1 & Metabolic",
    "5-amino-1mq": "GLP-1 & Metabolic",
    "tesamorelin": "Growth Hormone & Recovery",
    "sermorelin": "Growth Hormone & Recovery",
    "ipamorelin": "Growth Hormone & Recovery",
    "tesamorelin-ipamorelin": "Growth Hormone & Recovery",
    "cjc-1295-no-dac": "Growth Hormone & Recovery",
    "cjc-no-dac-ipamorelin": "Growth Hormone & Recovery",
    "hexarelin": "Growth Hormone & Recovery",
    "mots-c": "Growth Hormone & Recovery",
    "igf1-lr3": "Growth Hormone & Recovery",
    "bpc-157": "Healing & Repair Blends",
    "tb-500": "Healing & Repair Blends",
    "bpc-157-tb-500-wolverine": "Healing & Repair Blends",
    "glow-bpc-157-tb-500-ghk": "Healing & Repair Blends",
    "klow-kpv-bpc-157-tb-500-ghk": "Healing & Repair Blends",
    "kpv": "Healing & Repair Blends",
    "ghk-cu": "Healing & Repair Blends",
    "ll-37": "Healing & Repair Blends",
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
}
