from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.events import AuditEvent
from app.models.orders import Order
from app.models.payments import Payment
from app.services.payments import (
    PaymentActionError,
    mark_order_paid,
    mark_order_payment_failed,
)

# Re-exported so admin.py only needs one import for both the action
# functions and the error type they raise.
__all__ = [
    "AdminActionError",
    "AdminOrderRow",
    "AdminOrderDetail",
    "list_admin_orders",
    "get_admin_order_detail",
    "admin_mark_order_paid",
    "admin_mark_order_payment_failed",
]

AdminActionError = PaymentActionError


@dataclass(frozen=True)
class AdminOrderRow:
    order_id: uuid.UUID
    public_order_number: str
    customer_email: str
    customer_name: Optional[str]
    customer_phone: Optional[str]
    status: str
    total_cents: int
    currency: str
    created_at: str
    payment_provider: Optional[str]
    payment_status: Optional[str]


@dataclass(frozen=True)
class AdminOrderItemDetail:
    display_name_at_purchase: str
    sku_snapshot: str
    # What to order from the supplier — frozen at purchase time.
    supplier_sku_at_purchase: str
    supplier_name_at_purchase: str
    quantity: int
    unit_price_cents: int
    total_price_cents: int


@dataclass(frozen=True)
class AdminPaymentDetail:
    provider: str
    provider_payment_id: Optional[str]
    status: str
    amount_cents: int
    events: list[dict]


@dataclass(frozen=True)
class AdminOrderDetail:
    order_id: uuid.UUID
    public_order_number: str
    customer_email: str
    customer_name: Optional[str]
    customer_phone: Optional[str]
    status: str
    shipping_address: Optional[dict]
    subtotal_cents: int
    shipping_cents: int
    tax_cents: int
    total_cents: int
    currency: str
    created_at: str
    items: list[AdminOrderItemDetail]
    payments: list[AdminPaymentDetail]
    events: list[dict]


def _most_recent_payment(payments: list[Payment]) -> Optional[Payment]:
    if not payments:
        return None
    return max(payments, key=lambda payment: payment.created_at)


def list_admin_orders(session: Session) -> list[AdminOrderRow]:
    orders = list(
        session.execute(
            select(Order).options(selectinload(Order.payments)).order_by(Order.created_at.desc())
        ).scalars()
    )
    rows = []
    for order in orders:
        payment = _most_recent_payment(list(order.payments))
        rows.append(
            AdminOrderRow(
                order_id=order.id,
                public_order_number=order.public_order_number,
                customer_email=order.customer_email,
                customer_name=order.customer_name,
                customer_phone=order.customer_phone,
                status=order.status,
                total_cents=order.total_cents,
                currency=order.currency,
                created_at=order.created_at.isoformat(),
                payment_provider=payment.provider if payment else None,
                payment_status=payment.status if payment else None,
            )
        )
    return rows


def get_admin_order_detail(session: Session, order_id: uuid.UUID) -> Optional[AdminOrderDetail]:
    order = session.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.items),
            selectinload(Order.payments).selectinload(Payment.events),
            selectinload(Order.events),
        )
    ).scalar_one_or_none()
    if order is None:
        return None

    payments = sorted(order.payments, key=lambda payment: payment.created_at)
    events = sorted(order.events, key=lambda event: event.created_at)

    return AdminOrderDetail(
        order_id=order.id,
        public_order_number=order.public_order_number,
        customer_email=order.customer_email,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        status=order.status,
        shipping_address=order.shipping_address,
        subtotal_cents=order.subtotal_cents,
        shipping_cents=order.shipping_cents,
        tax_cents=order.tax_cents,
        total_cents=order.total_cents,
        currency=order.currency,
        created_at=order.created_at.isoformat(),
        items=[
            AdminOrderItemDetail(
                display_name_at_purchase=item.display_name_at_purchase,
                sku_snapshot=item.sku_snapshot,
                supplier_sku_at_purchase=item.supplier_sku_at_purchase,
                supplier_name_at_purchase=item.supplier_name_at_purchase,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                total_price_cents=item.total_price_cents,
            )
            for item in sorted(order.items, key=lambda item: item.created_at)
        ],
        payments=[
            AdminPaymentDetail(
                provider=payment.provider,
                provider_payment_id=payment.provider_payment_id,
                status=payment.status,
                amount_cents=payment.amount_cents,
                events=[
                    {"event_type": event.event_type, "data": event.data, "created_at": event.created_at.isoformat()}
                    for event in sorted(payment.events, key=lambda event: event.created_at)
                ],
            )
            for payment in payments
        ],
        events=[
            {"event_type": event.event_type, "data": event.data, "created_at": event.created_at.isoformat()}
            for event in events
        ],
    )


def _write_audit(session: Session, *, actor: str, action: str, entity_id: uuid.UUID, data: dict) -> None:
    session.add(AuditEvent(actor=actor, action=action, entity_type="order", entity_id=entity_id, data=data))
    session.flush()


def admin_mark_order_paid(
    session: Session,
    *,
    order_id: uuid.UUID,
    actor: str,
    provider: str,
    provider_payment_id: Optional[str],
    note: Optional[str],
) -> Order:
    """The launch flow (David, 9/4): an admin confirms a Venmo / Zelle
    transfer arrived and marks the order paid; with fulfillment_mode
    "manual" that is also the cue to place the order with the supplier
    by hand. Calls the exact same app.services.payments.mark_order_paid a
    future payment-provider webhook will call — only the caller differs."""
    order = mark_order_paid(
        session,
        order_id=order_id,
        provider=provider,
        provider_payment_id=provider_payment_id,
        source=f"admin:{actor}",
        note=note,
    )
    _write_audit(
        session,
        actor=actor,
        action="order.marked_paid",
        entity_id=order_id,
        data={"provider": provider, "provider_payment_id": provider_payment_id, "note": note},
    )
    return order


def admin_mark_order_payment_failed(
    session: Session, *, order_id: uuid.UUID, actor: str, reason: str
) -> Order:
    order = mark_order_payment_failed(session, order_id=order_id, source=f"admin:{actor}", reason=reason)
    _write_audit(
        session,
        actor=actor,
        action="order.marked_payment_failed",
        entity_id=order_id,
        data={"reason": reason},
    )
    return order
