from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.order_status import OrderStatus
from app.models.orders import Order, OrderEvent
from app.models.payments import Payment, PaymentEvent
from app.services.queue import enqueue_job


class PaymentActionError(RuntimeError):
    """Raised when a payment-status transition can't be applied — e.g. an
    order that's already been resolved (not still PAYMENT_PENDING), or a
    reference to an order that doesn't exist. Idempotency guard: this is
    what makes it safe for a real webhook to retry-deliver the same event
    later without double-enqueuing fulfillment or double-writing history.
    """


def _get_order_and_payment(session: Session, order_id: uuid.UUID) -> tuple[Order, Payment]:
    order = session.get(Order, order_id)
    if order is None:
        raise PaymentActionError(f"No such order: {order_id}")

    payment = session.execute(
        select(Payment).where(Payment.order_id == order_id).order_by(Payment.created_at.desc())
    ).scalars().first()
    if payment is None:
        raise PaymentActionError(f"Order {order_id} has no payment record.")

    return order, payment


def mark_order_paid(
    session: Session,
    *,
    order_id: uuid.UUID,
    provider: str,
    provider_payment_id: Optional[str],
    source: str,
    note: Optional[str] = None,
) -> Order:
    """Transitions an order PAYMENT_PENDING -> PAID and — critically —
    this is what enqueues submit_supplier_order, not order creation (see
    storefront.create_order's docstring). Fulfillment must never fire
    before payment has actually cleared.

    `source` records who/what triggered this — e.g. "admin:david" for
    today's interim manual-confirmation action, or a payment provider's
    key (e.g. "crypto"/"ach") once a real webhook calls this directly.
    That's the only thing that changes when a real webhook replaces the
    interim admin action: the caller, not this function.

    Idempotent: raises PaymentActionError (a no-op from the caller's
    perspective — nothing is written) if the order isn't still
    PAYMENT_PENDING, so a provider's retried webhook delivery can never
    double-enqueue fulfillment or double-write history.
    """
    order, payment = _get_order_and_payment(session, order_id)
    if order.status != OrderStatus.PAYMENT_PENDING:
        raise PaymentActionError(
            f"Order {order.public_order_number} is {order.status!r}, not PAYMENT_PENDING — refusing to mark paid again."
        )

    payment.status = "succeeded"
    payment.provider = provider
    payment.provider_payment_id = provider_payment_id

    session.add(
        PaymentEvent(
            payment_id=payment.id,
            event_type="payment.confirmed",
            data={"source": source, "note": note},
        )
    )

    order.status = OrderStatus.PAID
    session.add(
        OrderEvent(
            order_id=order.id,
            event_type="status_changed",
            data={"from": OrderStatus.PAYMENT_PENDING, "to": OrderStatus.PAID, "source": source},
        )
    )

    # Fulfillment only ever starts here, once payment has actually
    # cleared — never at order creation. In "supplier_api" mode that is
    # the worker's submit_supplier_order job; in the default "manual"
    # mode (David, 9/4) nothing is pushed anywhere — an admin places the
    # order with the supplier by hand — and the event below is the
    # record that the order is now waiting on a person.
    if get_settings().fulfillment_mode == "supplier_api":
        enqueue_job(session, job_type="submit_supplier_order", payload={"order_id": str(order.id)})
    else:
        session.add(
            OrderEvent(
                order_id=order.id,
                event_type="awaiting_manual_fulfillment",
                data={"source": source, "fulfillment_mode": get_settings().fulfillment_mode},
            )
        )

    session.flush()
    return order


def mark_order_payment_failed(
    session: Session,
    *,
    order_id: uuid.UUID,
    source: str,
    reason: str,
) -> Order:
    """Transitions an order PAYMENT_PENDING -> PAYMENT_FAILED. Never
    enqueues fulfillment. Same idempotency guard as mark_order_paid."""
    order, payment = _get_order_and_payment(session, order_id)
    if order.status != OrderStatus.PAYMENT_PENDING:
        raise PaymentActionError(
            f"Order {order.public_order_number} is {order.status!r}, not PAYMENT_PENDING — refusing to mark failed."
        )

    payment.status = "failed"

    session.add(
        PaymentEvent(
            payment_id=payment.id,
            event_type="payment.failed",
            data={"source": source, "reason": reason},
        )
    )

    order.status = OrderStatus.PAYMENT_FAILED
    session.add(
        OrderEvent(
            order_id=order.id,
            event_type="status_changed",
            data={"from": OrderStatus.PAYMENT_PENDING, "to": OrderStatus.PAYMENT_FAILED, "source": source},
        )
    )

    session.flush()
    return order
