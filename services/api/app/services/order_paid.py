"""What happens once an order is PAID, whoever confirmed it.

David, 9/10: a Bitcoin order confirmed by OpenNode's webhook must look
to staff exactly like a Venmo/Zelle order confirmed with Mark paid, so
both paths run this same best-effort fan-out after their commit:

1. The Google Sheet row for the order is rewritten in place
   (order_sheet.update_order_row) — status PAID, payment_status
   succeeded, payment_method — never a second row.
2. GoHighLevel gets the customer-safe payload with `event: "order.paid"`
   on its own inbound webhook (GHL_ORDER_PAID_WEBHOOK_URL) so a
   separate workflow can email the payment confirmation. Blank URL = no
   push.

Runs as a FastAPI background task with its own session (the request's
session is closed by then), each step isolated: a Sheets outage never
stops the GHL push, and nothing here can raise into the caller. There
is no retry — the admin orders page and the CSV export are the durable
record; this is the mirror.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.orders import Order
from app.services import ghl_notify, order_sheet
from app.services.order_export import order_notification_payload

logger = logging.getLogger(__name__)


def build_paid_payload(order_id: uuid.UUID) -> dict | None:
    """Load the order fresh and build the "order.paid" notification row,
    or None when the order does not exist."""
    session = SessionLocal()
    try:
        order = session.execute(
            select(Order)
            .options(selectinload(Order.items), selectinload(Order.payments))
            .where(Order.id == order_id)
        ).scalar_one_or_none()
        if order is None:
            logger.warning("order-paid fan-out: no such order %s", order_id)
            return None
        site = get_settings().public_site_url.strip().rstrip("/")
        order_url = f"{site}/order/{order.access_token}" if site else None
        return order_notification_payload(order, order_url=order_url, event="order.paid")
    finally:
        session.close()


def _push_ghl_paid(payload: dict) -> bool:
    ghl = ghl_notify.ghl_payload(payload)
    if not ghl:
        return False
    return ghl_notify.push_order_to_ghl(ghl, url=get_settings().ghl_order_paid_webhook_url)


def run_order_paid_fanout(order_id: uuid.UUID) -> None:
    """Best-effort side effects for a newly PAID order. Safe to call
    more than once: the sheet write is a rewrite, and the GHL push is
    fire-and-forget."""
    try:
        payload = build_paid_payload(order_id)
    except Exception:
        logger.exception("order-paid fan-out: could not load order %s", order_id)
        return
    if payload is None:
        return
    order_number = payload.get("order_number")
    for name, step in (
        ("sheet update", lambda: order_sheet.update_order_row(payload)),
        ("GHL paid push", lambda: _push_ghl_paid(payload)),
    ):
        try:
            step()
        except Exception:
            logger.exception("order-paid fan-out: %s failed for %s", name, order_number)
