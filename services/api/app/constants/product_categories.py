"""Source of truth for Product.category across the LYO ladder catalog.

Product.category is a free String(100) column with no DB enum or CHECK
constraint (see catalog.py), so nothing stops a bad value being written.
This module is the value set everything else agrees on.

Why this exists at all: the catalog importer stamps a category at product
*creation* time from whichever price-sheet tab first produced the row
("RUO Pens", "RUO Vials", "RUO Lyophilized") and never updates it again.
Those labels describe the supplier's sheet layout, not what TimeChain
sells. After David's 2026-08-22 lyophilized-only decision they became
actively wrong: 21 of the 32 sellable products were labeled "RUO Pens"
while every sellable variant is form="lyophilized" (pens, vials,
preconstituted and rx are all rejected outright by
ProductVariant._validate_is_sellable). A customer-facing nav that reads
"RUO Pens (21)" on a storefront that sells zero pens is a factual
misstatement, so the recategorize migration exists to fix it.

Two consumers must agree with this module or the taxonomy silently drifts:

- alembic revision d4e5f6a7b8c9 applied this mapping to the existing
  rows. It deliberately embeds a *frozen copy* of the pairs below rather
  than importing this module — an already-applied migration whose
  behaviour changes when a constant is edited is not reproducible. If you
  edit the mapping here, write a NEW migration; do not edit that one.
- app.scripts.sync_lyo_catalog imports PRODUCT_CATEGORY_BY_SLUG (it used
  to carry its own private copy) so a re-run after a catalog re-import
  normalizes fresh rows to the same taxonomy instead of reverting them.

apps/web/src/lib/categories.ts mirrors LAUNCH_CATEGORIES for the footer's
static links; that file names this one as canonical.
"""

# Display order for any UI that renders the full list. Note that this is
# also plain alphabetical order, which is what GET /shop/filter-options
# returns (it sorts the distinct values it finds). That coincidence is
# convenient — Supplies lands last on its own merits — but it is a
# coincidence: if a future category would sort ahead of where it should
# read, the nav needs an explicit order, not a re-sort of the API result.
LAUNCH_CATEGORIES: list[str] = [
    "GLP-1 & Metabolic",
    "Growth Hormone & Recovery",
    "Healing & Repair Blends",
    "Longevity & Cognitive",
    "Sexual Health & Hormonal",
    "Supplies",
]

# All 35 ladder slugs, not just the 32 currently sellable. ghrp-6,
# kisspeptin and tesamorelin-ipamorelin have no verified lyophilized
# supplier mapping yet and so are not live; keeping them here means they
# arrive pre-categorized the moment admin approval makes them sellable,
# rather than showing up under a stale import label.
PRODUCT_CATEGORY_BY_SLUG: dict[str, str] = {
    "glp-1s": "GLP-1 & Metabolic",
    "glp-2t": "GLP-1 & Metabolic",
    "glp-3r": "GLP-1 & Metabolic",
    "cagrilinitide": "GLP-1 & Metabolic",
    "aod-9604": "GLP-1 & Metabolic",
    "tesamorelin": "Growth Hormone & Recovery",
    "sermorelin": "Growth Hormone & Recovery",
    "ipamorelin": "Growth Hormone & Recovery",
    "tesamorelin-ipamorelin": "Growth Hormone & Recovery",
    "cjc-no-dac-ipamorelin": "Growth Hormone & Recovery",
    "ghrp-2": "Growth Hormone & Recovery",
    "ghrp-6": "Growth Hormone & Recovery",
    "mots-c": "Growth Hormone & Recovery",
    "bpc-157": "Healing & Repair Blends",
    "tb-500": "Healing & Repair Blends",
    "bpc-157-tb-500-wolverine": "Healing & Repair Blends",
    "glow-bpc-157-tb-500-ghk": "Healing & Repair Blends",
    "klow-kpv-bpc-157-tb-500-ghk": "Healing & Repair Blends",
    "kpv": "Healing & Repair Blends",
    "ghk-cu": "Healing & Repair Blends",
    "ghk-cu-kpv": "Healing & Repair Blends",
    "nad": "Longevity & Cognitive",
    "epithalon": "Longevity & Cognitive",
    "ss-31": "Longevity & Cognitive",
    "ta-1": "Longevity & Cognitive",
    "dsip": "Longevity & Cognitive",
    "selank": "Longevity & Cognitive",
    "semax": "Longevity & Cognitive",
    "kisspeptin": "Longevity & Cognitive",
    "igf1-lr3": "Longevity & Cognitive",
    "pt-141": "Sexual Health & Hormonal",
    "mt-1": "Sexual Health & Hormonal",
    "mt-2": "Sexual Health & Hormonal",
    "hcg-6000-units": "Sexual Health & Hormonal",
    "bac-water": "Supplies",
}
