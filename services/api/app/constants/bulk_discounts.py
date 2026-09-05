"""Quantity discount tiers: buy N vials of the *same* variant (same
product, same strength — not N total items across different variants),
get a flat percentage off that line's unit price. Applies uniformly
across every SKU (no per-product overrides) — confirmed against "TimeChain
RUO LYO - Volume Ladder + Affiliate Margins v3 8.22.26", sheet 3: every
row there is exactly list price * (1 - percent_off/100), floored to the
cent.

Single source of truth — app.services.storefront (the only place a price
is ever computed) reads this to discount unit_price_cents; the
/shop/bulk-discount-tiers endpoint exposes it read-only so the frontend
can render a "buy more, save more" table without hardcoding percentages
that could drift from what checkout actually charges.

Ordered highest-quantity-first so callers can `next(t for t in TIERS if
quantity >= t.min_quantity)` and get the best tier the customer qualifies
for.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BulkDiscountTier:
    min_quantity: int
    percent_off: int


BULK_DISCOUNT_TIERS: list[BulkDiscountTier] = [
    BulkDiscountTier(min_quantity=20, percent_off=20),
    BulkDiscountTier(min_quantity=15, percent_off=18),
    BulkDiscountTier(min_quantity=10, percent_off=15),
    BulkDiscountTier(min_quantity=5, percent_off=10),
]


def percent_off_for_quantity(quantity: int) -> int:
    for tier in BULK_DISCOUNT_TIERS:
        if quantity >= tier.min_quantity:
            return tier.percent_off
    return 0


def discounted_unit_price_cents(retail_price_cents: int, quantity: int) -> int:
    """Integer-cents floor, matching the source pricing sheet exactly
    (verified against every row of sheet 3) — never float math, same
    discipline as every other money computation in this codebase."""
    percent_off = percent_off_for_quantity(quantity)
    return retail_price_cents - (retail_price_cents * percent_off // 100)
