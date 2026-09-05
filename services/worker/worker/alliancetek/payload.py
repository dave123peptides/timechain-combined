from __future__ import annotations

from datetime import datetime
from typing import Any


def _build_address(shipping_address: dict[str, Any]) -> dict[str, Any]:
    """Maps our shipping_address shape (line1/line2/city/region/
    postal_code/country) onto ShipStation-custom-store-API address field
    names. Deliberately has no `name` key — checkout never collects a
    customer name (only email + address), so there's nothing to put
    there. Not fabricated as an empty string: if AllianceTek's API
    requires `name`, that's a real gap needing a checkout field, not
    something to paper over here.
    """
    return {
        "street1": shipping_address.get("line1", ""),
        "street2": shipping_address.get("line2") or "",
        "city": shipping_address.get("city", ""),
        "state": shipping_address.get("region", ""),
        "postalCode": shipping_address.get("postal_code", ""),
        "country": shipping_address.get("country", ""),
    }


def _build_item(item: dict[str, Any]) -> dict[str, Any]:
    """Reads only the immutable *_at_purchase snapshot fields — never
    Product.name, never a live SupplierProduct/SupplierProductMapping
    join. `item` is a plain dict pulled from order_items via the
    worker's hand-mirrored Core table, so there's nothing Product-shaped
    even in scope to read by mistake (same guarantee as
    app/services/supplier_payload.py's build_supplier_order_line on the
    api side).

    unitPrice is the one deliberate exception to this codebase's "cents
    everywhere" rule — ShipStation-custom-store-API naming conventionally
    expects a decimal dollar amount, not integer cents.
    """
    return {
        "sku": item["supplier_sku_at_purchase"],
        "name": item["supplier_name_at_purchase"],
        "quantity": item["quantity"],
        "unitPrice": round(item["unit_price_cents"] / 100, 2),
    }


def build_order_payload(order: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    """Builds the AllianceTek create/update-order payload for one
    TimeChain order.

    `order["public_order_number"]` becomes `orderNumber` — per
    AllianceTek's confirmed idempotency rule, this value must be the
    same on every retry of the same order (never regenerated), which is
    exactly what makes create_update_order idempotent instead of
    duplicating the supplier order. See
    worker/jobs/submit_supplier_order.py, which is the only caller that
    should ever invoke this function.

    `order` and each entry in `items` are plain dicts, not ORM
    objects — this function has no session and no model imports, so it
    is structurally incapable of reading anything beyond the keys it
    actually accesses.
    """
    order_date = order["created_at"]
    if isinstance(order_date, datetime):
        order_date = order_date.isoformat()

    address = _build_address(order.get("shipping_address") or {})

    return {
        "orderNumber": order["public_order_number"],
        "orderDate": order_date,
        "orderStatus": "awaiting_shipment",
        "billTo": address,
        "shipTo": address,
        "items": [_build_item(item) for item in items],
    }
