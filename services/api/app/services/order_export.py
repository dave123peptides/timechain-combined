"""One flat, spreadsheet-shaped view of an order, used three ways:

- the admin CSV export (GET /admin/orders/export.csv),
- the new-order webhook payload (app/services/order_notify.py),
- the admin orders page's detail rows.

Manual fulfillment (David, 9/4) means a person reads this and places
the order with the supplier by hand, so every column is what that
person needs: who ordered, where it ships, what to order (the supplier
SKU and name frozen on each line at purchase time — never a live join,
see OrderItem's docstring), what they owe, and how they said they'd pay.
"""

from __future__ import annotations

import csv
import io
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.orders import Order
from app.models.payments import Payment

# Column order is shared with the vial site (~/Desktop/timechain), whose
# TCP- orders land in the same "Timechain Orders" sheet: both apps must
# write the same layout or their rows misalign. discount_code (column B,
# added 9/6) is the vial site's checkout discount code; pens have no
# discount codes yet, so this app writes it empty.
EXPORT_COLUMNS = [
    "order_number",
    "discount_code",
    "placed_at",
    "status",
    "payment_method",
    "payment_status",
    "customer_name",
    "customer_phone",
    "customer_email",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal_code",
    "country",
    "item_count",
    "items",
    "subtotal",
    "shipping",
    "tax",
    "total",
    "currency",
]


def _money(cents: int) -> str:
    return f"{cents / 100:.2f}"


def _latest_payment(order: Order) -> Optional[Payment]:
    payments = list(order.payments or [])
    if not payments:
        return None
    return max(payments, key=lambda p: (p.created_at, str(p.id)))


def order_export_row(order: Order) -> dict:
    """The flat record for one order. Items are one string —
    "2 × BPC-157 20mg pen [supplier: PENDING-TC-BPC-157-PEN-20 · BPC-157 20mg]" —
    joined with " | ", so a row stays one order in a spreadsheet."""
    address = order.shipping_address or {}
    payment = _latest_payment(order)
    items = sorted(order.items, key=lambda item: item.created_at)
    return {
        "order_number": order.public_order_number,
        "placed_at": order.created_at.isoformat(),
        "status": order.status,
        "payment_method": payment.provider if payment else "",
        "payment_status": payment.status if payment else "",
        "customer_name": order.customer_name or "",
        "customer_phone": order.customer_phone or "",
        "customer_email": order.customer_email,
        "address_line1": address.get("line1", ""),
        "address_line2": address.get("line2") or "",
        "city": address.get("city", ""),
        "state": address.get("region", ""),
        "postal_code": address.get("postal_code", ""),
        "country": address.get("country", ""),
        "item_count": sum(item.quantity for item in items),
        "items": " | ".join(
            f"{item.quantity} × {item.display_name_at_purchase} "
            f"[supplier: {item.supplier_sku_at_purchase} · {item.supplier_name_at_purchase}]"
            for item in items
        ),
        "subtotal": _money(order.subtotal_cents),
        "shipping": _money(order.shipping_cents),
        "tax": _money(order.tax_cents),
        "total": _money(order.total_cents),
        "currency": order.currency.upper(),
        "discount_code": "",
    }


def order_notification_payload(order: Order, *, order_url: Optional[str] = None) -> dict:
    """The webhook body: the flat row plus the items as structured
    objects (a Sheet gets the row; anything smarter can use the list)."""
    row = order_export_row(order)
    row["items_detail"] = [
        {
            "name": item.display_name_at_purchase,
            "quantity": item.quantity,
            "sku": item.sku_snapshot,
            "supplier_sku": item.supplier_sku_at_purchase,
            "supplier_name": item.supplier_name_at_purchase,
            "unit_price": _money(item.unit_price_cents),
            "total_price": _money(item.total_price_cents),
        }
        for item in sorted(order.items, key=lambda item: item.created_at)
    ]
    if order_url:
        row["order_url"] = order_url
    return row


def list_export_rows(session: Session, *, status: Optional[str] = None) -> list[dict]:
    query = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.payments))
        .order_by(Order.created_at.desc())
    )
    if status:
        query = query.where(Order.status == status)
    orders = session.execute(query).scalars()
    return [order_export_row(order) for order in orders]


def rows_to_csv(rows: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS, extrasaction="ignore", lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()
