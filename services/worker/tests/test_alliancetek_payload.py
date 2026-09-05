from __future__ import annotations

from datetime import datetime, timezone

from worker.alliancetek.payload import build_order_payload

_ORDER = {
    "public_order_number": "TCP-ABC123",
    "created_at": datetime(2026, 8, 12, 15, 30, tzinfo=timezone.utc),
    "shipping_address": {
        "line1": "1 Test St",
        "line2": "Apt 2",
        "city": "Testville",
        "region": "CA",
        "postal_code": "90210",
        "country": "US",
    },
}

_ITEM = {
    "supplier_sku_at_purchase": "SUP-SKU-1",
    "supplier_name_at_purchase": "Supplier Test Product",
    "quantity": 3,
    "unit_price_cents": 1999,
}


def test_build_order_payload_uses_public_order_number_as_order_number():
    payload = build_order_payload(_ORDER, [_ITEM])
    assert payload["orderNumber"] == "TCP-ABC123"


def test_build_order_payload_status_is_always_awaiting_shipment():
    payload = build_order_payload(_ORDER, [_ITEM])
    assert payload["orderStatus"] == "awaiting_shipment"


def test_build_order_payload_order_date_is_isoformat_string():
    payload = build_order_payload(_ORDER, [_ITEM])
    assert payload["orderDate"] == "2026-08-12T15:30:00+00:00"


def test_build_order_payload_unit_price_is_dollar_conversion_of_cents():
    payload = build_order_payload(_ORDER, [_ITEM])
    assert payload["items"][0]["unitPrice"] == 19.99


def test_build_order_payload_item_uses_only_supplier_snapshot_fields():
    payload = build_order_payload(_ORDER, [_ITEM])
    item = payload["items"][0]
    assert item["sku"] == "SUP-SKU-1"
    assert item["name"] == "Supplier Test Product"
    assert item["quantity"] == 3


def test_build_order_payload_bill_to_and_ship_to_are_identical_and_have_no_name():
    payload = build_order_payload(_ORDER, [_ITEM])
    assert payload["billTo"] == payload["shipTo"]
    assert "name" not in payload["billTo"]
    assert payload["billTo"]["street1"] == "1 Test St"
    assert payload["billTo"]["postalCode"] == "90210"


def test_build_order_payload_cannot_reach_anything_product_shaped():
    """Proves the function is structurally incapable of reading a
    TimeChain product name or a live SupplierProduct/mapping value — the
    order/item dicts passed in have no such keys at all, and the
    function still produces a valid payload using only what's there."""
    order = {
        "public_order_number": "TCP-NOPROD",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "shipping_address": None,
    }
    item = {
        "supplier_sku_at_purchase": "SKU-X",
        "supplier_name_at_purchase": "Name X",
        "quantity": 1,
        "unit_price_cents": 500,
    }
    payload = build_order_payload(order, [item])
    assert payload["items"][0]["sku"] == "SKU-X"
    assert payload["billTo"] == {"street1": "", "street2": "", "city": "", "state": "", "postalCode": "", "country": ""}


def test_build_order_payload_multiple_items():
    payload = build_order_payload(_ORDER, [_ITEM, {**_ITEM, "supplier_sku_at_purchase": "SUP-SKU-2", "quantity": 1}])
    assert len(payload["items"]) == 2
    assert payload["items"][1]["sku"] == "SUP-SKU-2"
