"""Shared display labels for ProductVariant.form (a free String(20)
column, no DB enum/CHECK constraint — see catalog.py). Single source of
truth: storefront.py and admin_products.py previously each kept their own
copy of this dict, which is exactly the kind of drift trap that let
`preconstituted` slip through unrecognized in one place but not another.
"""

FORM_LABEL = {
    "pen": "Pen",
    "vial": "Vial",
    "lyophilized": "Lyophilized",
    "preconstituted": "Preconstituted",
    "rx_vial": "Rx Vial",
    "other": "Other",
}
