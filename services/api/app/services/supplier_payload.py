from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.catalog import SupplierProductMapping


def build_supplier_order_line(mapping: "SupplierProductMapping", *, quantity: int, unit_price_cents: int) -> dict:
    """Builds one supplier order line from a verified variant<->supplier
    mapping.

    Deliberately takes ONLY a `SupplierProductMapping` — never a `Product`
    or `ProductVariant` — and reads only `mapping.supplier_sku` /
    `mapping.supplier_name`. That's not just a convention: the function
    has no other way to reach a TimeChain display name even by mistake,
    since nothing Product-shaped is ever in scope. `quantity` and
    `unit_price_cents` come from the immutable order-item snapshot
    (`OrderItem.quantity` / `unit_price_cents`), passed as plain values so
    this function can't reach into an OrderItem's `name_snapshot` either.

    `unit_price_cents` matches the "integer cents, never float" rule used
    for every money column in this schema; AllianceTek's actual expected
    unit for an outbound order payload hasn't been confirmed yet (same
    "don't guess a payload shape from an unconfirmed API" caution as
    `worker/supplier_sync/mapping.py`'s `_coerce_price_cents`), so this key
    is named `unitPriceCents` rather than assuming dollars.
    """
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity!r}")
    if unit_price_cents < 0:
        raise ValueError(f"unit_price_cents must be non-negative, got {unit_price_cents!r}")

    return {
        "sku": mapping.supplier_sku,
        "name": mapping.supplier_name,
        "quantity": quantity,
        "unitPriceCents": unit_price_cents,
    }
