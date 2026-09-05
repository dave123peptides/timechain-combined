"""Advisory-only suggested values for Product.category (a free String(100)
column, no DB enum/CHECK constraint — see catalog.py). This is NOT
enforced anywhere: it exists purely so a future admin product-content UI
can offer a dropdown of known-good values instead of letting free-text
entry drift ("Peptides" vs "peptide" vs "Peptide "). The shop-page
category filter (GET /shop/products?category=) does not depend on this
list — it derives its filter options dynamically from whatever category
values are actually present in the sellable catalog, so it works
regardless of what the real catalog ends up using.

This used to carry its own list of import-era labels ("RUO Vials", "RUO
Pens", "Prescription", ...). Those described the supplier price sheet's
tab layout rather than the storefront, and alembic revision d4e5f6a7b8c9
replaced them on every row. It now re-exports the real taxonomy so an
admin dropdown can never suggest a value the catalog no longer uses.
"""

from app.constants.product_categories import LAUNCH_CATEGORIES

CATEGORIES: list[str] = LAUNCH_CATEGORIES
