from __future__ import annotations

from typing import Any, Optional

_MISSING = object()

# `productId` is the one field name AllianceTek has confirmed. The others
# below haven't been confirmed against a real payload yet, so each checks
# a handful of likely candidate names and fails loudly — naming the
# productId and the raw keys that *were* present — if none match, rather
# than silently inserting wrong or blank data. Narrow these lists (or add
# to them) once a real payload is on hand; `raw_payload` on the row keeps
# the full record either way, so nothing is lost by failing here.
_SKU_KEYS = ("sku", "productSku", "SKU", "Sku")
_NAME_KEYS = ("name", "productName", "Name", "title", "Title")
_ACTIVE_KEYS = ("active", "isActive", "Active", "IsActive", "status", "Status")
_PRICE_KEYS = ("price", "wholesalePrice", "cost", "Price", "WholesalePrice", "Cost")


class SupplierProductFieldError(RuntimeError):
    """Raised when a supplier product record is missing a required field
    under every candidate name we know to check, or has a value we can't
    confidently interpret."""


def _first_present(raw: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    return _MISSING


def _coerce_bool(value: Any, *, product_id: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("true", "1", "yes", "active", "y"):
            return True
        if normalized in ("false", "0", "no", "inactive", "n"):
            return False
    raise SupplierProductFieldError(
        f"Could not interpret active-status value {value!r} for supplier productId={product_id}."
    )


def _coerce_price_cents(value: Any) -> Optional[int]:
    """Assumes supplier price fields, if present, are already integer
    cents. A float/decimal dollar amount would need explicit handling
    once the real payload confirms the units — deliberately not guessing
    here, since misreading dollars as cents (or vice versa) is exactly
    the kind of silent money bug we don't want."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def map_supplier_product(raw: dict[str, Any], *, supplier_key: str = "umsrx") -> dict[str, Any]:
    """Maps one raw AllianceTek product record to a `supplier_products`
    row, stamped with the pharmacy account it came from.

    Raises `SupplierProductFieldError` (rather than guessing) if a
    required field can't be found under any known candidate name.
    """
    if "productId" not in raw or raw["productId"] is None:
        raise SupplierProductFieldError(
            f"Supplier product record has no 'productId' field. Raw keys: {sorted(raw.keys())}"
        )
    product_id = raw["productId"]

    sku = _first_present(raw, _SKU_KEYS)
    if sku is _MISSING:
        raise SupplierProductFieldError(
            f"No SKU field found for supplier productId={product_id} "
            f"(checked {_SKU_KEYS}). Raw keys: {sorted(raw.keys())}"
        )

    name = _first_present(raw, _NAME_KEYS)
    if name is _MISSING:
        raise SupplierProductFieldError(
            f"No name field found for supplier productId={product_id} "
            f"(checked {_NAME_KEYS}). Raw keys: {sorted(raw.keys())}"
        )

    active_raw = _first_present(raw, _ACTIVE_KEYS)
    if active_raw is _MISSING:
        raise SupplierProductFieldError(
            f"No active-status field found for supplier productId={product_id} "
            f"(checked {_ACTIVE_KEYS}). Raw keys: {sorted(raw.keys())}"
        )

    price_raw = _first_present(raw, _PRICE_KEYS)
    price_cents = None if price_raw is _MISSING else _coerce_price_cents(price_raw)

    return {
        "supplier_product_id": int(product_id),
        "supplier_key": supplier_key,
        # TEXT, not int — SKUs can contain letters/hyphens (e.g. "5AM1-50").
        "supplier_sku": str(sku),
        "supplier_name": str(name),
        "supplier_active": _coerce_bool(active_raw, product_id=product_id),
        "supplier_price_cents": price_cents,
        "raw_payload": raw,
    }
