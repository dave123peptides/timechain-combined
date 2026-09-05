from __future__ import annotations

import pytest

from app.services.supplier_payload import build_supplier_order_line


class _LeakProofMapping:
    """A stand-in for SupplierProductMapping whose only real attributes
    are supplier_sku/supplier_name — anything else (e.g. .product_variant,
    .product, .id) raises. If build_supplier_order_line only ever reads
    what it's supposed to, this object works exactly like the real thing.
    """

    def __init__(self, supplier_sku: str, supplier_name: str) -> None:
        self.supplier_sku = supplier_sku
        self.supplier_name = supplier_name

    def __getattr__(self, item: str):
        raise AssertionError(f"build_supplier_order_line must never access .{item}")


def test_build_supplier_order_line_uses_mapping_sku_and_name():
    mapping = _LeakProofMapping(supplier_sku="5AM1-50", supplier_name="5 Amino 1mq 50mg 3mL Pen")
    line = build_supplier_order_line(mapping, quantity=2, unit_price_cents=1999)
    assert line == {
        "sku": "5AM1-50",
        "name": "5 Amino 1mq 50mg 3mL Pen",
        "quantity": 2,
        "unitPriceCents": 1999,
    }


def test_build_supplier_order_line_cannot_reach_anything_product_shaped():
    """Proves the safety property directly: a mapping-like object that
    raises on any attribute access other than supplier_sku/supplier_name
    still works, meaning the function body never dereferences
    .product_variant, .product, or any TimeChain display name."""
    mapping = _LeakProofMapping(supplier_sku="ABC-1", supplier_name="Widget 10mg")
    line = build_supplier_order_line(mapping, quantity=1, unit_price_cents=500)
    assert line["sku"] == "ABC-1"
    assert line["name"] == "Widget 10mg"


def test_build_supplier_order_line_rejects_non_positive_quantity():
    mapping = _LeakProofMapping(supplier_sku="ABC-1", supplier_name="Widget 10mg")
    with pytest.raises(ValueError):
        build_supplier_order_line(mapping, quantity=0, unit_price_cents=500)


def test_build_supplier_order_line_rejects_negative_price():
    mapping = _LeakProofMapping(supplier_sku="ABC-1", supplier_name="Widget 10mg")
    with pytest.raises(ValueError):
        build_supplier_order_line(mapping, quantity=1, unit_price_cents=-1)
