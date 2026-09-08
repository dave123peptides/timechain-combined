"""Checkout discount codes. A code typed at checkout takes a flat
percentage off the merchandise subtotal (after bulk tiers), before
shipping and tax. Matching is case-insensitive and ignores surrounding
whitespace ("NATALIE", "natalie" and " Natalie " are the same code).

Single source of truth — app.services.storefront applies it in
build_quote and create_order, the only two places a total is ever
computed, and snapshots the normalized code plus the cents taken off onto
the Order so the status page, admin, CSV and order sheet all agree.

Codes: NATALIE, 10% off (David, 9/6); TRUTH, 10% off (David, 9/7).
Add a code by adding a row;
removing one only stops new orders using it (placed orders keep their
snapshot).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DiscountCode:
    code: str
    percent_off: int


DISCOUNT_CODES: dict[str, DiscountCode] = {
    "NATALIE": DiscountCode(code="NATALIE", percent_off=10),
    "TRUTH": DiscountCode(code="TRUTH", percent_off=10),
}


def normalize_discount_code(raw: Optional[str]) -> str:
    return (raw or "").strip().upper()


def find_discount_code(raw: Optional[str]) -> Optional[DiscountCode]:
    return DISCOUNT_CODES.get(normalize_discount_code(raw))


def discount_cents_for(subtotal_cents: int, percent_off: int) -> int:
    """Integer-cents floor — never float math, same discipline as
    app.constants.bulk_discounts."""
    return subtotal_cents * percent_off // 100
