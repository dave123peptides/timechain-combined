from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from worker.alliancetek.client import AllianceTekClient, SupplierApiConfigError, SupplierApiError
from worker.alliancetek.errors import RETRY_DELAYS_SECONDS, SupplierErrorClass, classify_supplier_error
from worker.alliancetek.payload import build_order_payload
from worker.config import get_settings
from worker.db import (
    order_events_table,
    order_items_table,
    orders_table,
    supplier_attempts_table,
    supplier_orders_table,
    supplier_products_table,
)
from worker.order_status import OrderStatus, SupplierOrderStatus
from worker.queue.provider import QueueProvider

logger = logging.getLogger("timechain.worker.jobs.submit_supplier_order")

_PROVIDER = "alliancetek"


def _route_to_manual_review(engine: Engine, *, order: sa.RowMapping, supplier_order_id: uuid.UUID, reason: str) -> None:
    """Sets both SupplierOrder.status and Order.status to MANUAL_REVIEW —
    called when a supplier error is permanent (bad SKU/name/payload/
    address, auth error, or our own missing config) or every retry tier
    has been exhausted. Writes an order_events row so the transition is
    visible in the order's audit trail, not just inferred from the
    current status value."""
    with engine.begin() as conn:
        conn.execute(
            sa.update(supplier_orders_table)
            .where(supplier_orders_table.c.id == supplier_order_id)
            .values(status=SupplierOrderStatus.MANUAL_REVIEW, updated_at=sa.func.now())
        )
        conn.execute(
            sa.update(orders_table)
            .where(orders_table.c.id == order["id"])
            .values(status=OrderStatus.MANUAL_REVIEW, updated_at=sa.func.now())
        )
        conn.execute(
            sa.insert(order_events_table).values(
                order_id=order["id"],
                event_type="status_changed",
                data={"from": order["status"], "to": OrderStatus.MANUAL_REVIEW, "reason": reason},
            )
        )
    logger.warning(
        "submit_supplier_order: order %s routed to MANUAL_REVIEW: %s", order["public_order_number"], reason
    )


def handle(
    payload: dict[str, Any], engine: Engine, queue: QueueProvider, *, client: Optional[AllianceTekClient] = None
) -> None:
    """job_type="submit_supplier_order". payload: {"order_id": "<uuid>",
    "supplier_retry_count": <int, optional, defaults to 0>}.

    Reads order + order_items via the immutable *_at_purchase snapshot
    columns only (see worker/alliancetek/payload.py) — never a live
    catalog/mapping join, so a catalog edit made after the order was
    placed can never change what gets submitted here.

    supplier_order_number always equals order.public_order_number and is
    reused verbatim on every retry — AllianceTek confirmed orderNumber is
    idempotent (resubmitting the same value updates the existing
    supplier order rather than creating a duplicate) — so a retried job
    reuses the same SupplierOrder row instead of creating a second one;
    only a new SupplierAttempt is appended per attempt, giving a full
    audit trail of every submission (including every retry).

    On failure, this classifies the error (see worker/alliancetek/errors.py)
    rather than relying on the queue's generic visibility-timeout retry:
    - Transient (429/500/502/503/504, connect/read timeout, generic
      network failure) and retry tiers remain: re-enqueues itself with
      supplier_retry_count incremented and delay_seconds set to the next
      tier in RETRY_DELAYS_SECONDS (immediate, 30s, 2m, 10m, 30m).
    - Permanent (bad SKU/name/payload/address, auth error, or our own
      missing config) or every tier already exhausted: routes both
      SupplierOrder.status and Order.status to MANUAL_REVIEW and stops.
    Either way this handler returns normally (never re-raises) — the
    current job delivery is deleted as a normal success, and any retry
    is a *new*, explicitly delayed job. Only a genuinely unexpected
    exception (not a classified supplier error) propagates, falling back
    to main.py's generic leave-in-queue retry.
    """
    settings = get_settings()
    if not settings.supplier_push_enabled:
        logger.info(
            "submit_supplier_order: SUPPLIER_PUSH_ENABLED=false; skipping order %s without contacting AllianceTek",
            payload["order_id"],
        )
        return

    order_id = uuid.UUID(payload["order_id"])
    supplier_retry_count = payload.get("supplier_retry_count", 0)
    owns_client = client is None

    try:
        with engine.begin() as conn:
            order = conn.execute(
                sa.select(orders_table).where(orders_table.c.id == order_id)
            ).mappings().one()
            items = list(
                conn.execute(
                    sa.select(order_items_table).where(order_items_table.c.order_id == order_id)
                ).mappings()
            )

            existing = conn.execute(
                sa.select(supplier_orders_table).where(
                    supplier_orders_table.c.order_id == order_id,
                    supplier_orders_table.c.provider == _PROVIDER,
                )
            ).mappings().one_or_none()

            if existing is None:
                # Which pharmacy fulfills this order? Resolved from the
                # supplier_products row backing the first line item's
                # purchase snapshot (the two catalogs are disjoint, so one
                # item identifies the supplier; mixed-supplier carts are
                # not supported by the middleware's per-account orders).
                supplier_key = None
                if items:
                    supplier_key = conn.execute(
                        sa.select(supplier_products_table.c.supplier_key).where(
                            supplier_products_table.c.supplier_product_id
                            == items[0]["supplier_product_id_at_purchase"]
                        )
                    ).scalar_one_or_none()
                supplier_order_id = uuid.uuid4()
                conn.execute(
                    sa.insert(supplier_orders_table).values(
                        id=supplier_order_id,
                        order_id=order_id,
                        supplier_order_number=order["public_order_number"],
                        provider=_PROVIDER,
                        supplier_key=supplier_key,
                        status=SupplierOrderStatus.PENDING,
                        currency=order["currency"],
                    )
                )
            else:
                supplier_order_id = existing["id"]
                # Retries always go back to the pharmacy the first attempt
                # went to — orderNumber is idempotent per account.
                supplier_key = existing["supplier_key"]

            next_attempt_number = conn.execute(
                sa.select(
                    sa.func.coalesce(sa.func.max(supplier_attempts_table.c.attempt_number), 0) + 1
                ).where(supplier_attempts_table.c.supplier_order_id == supplier_order_id)
            ).scalar_one()

        if client is None:
            client = (
                AllianceTekClient.from_settings_for_supplier(settings, supplier_key)
                if supplier_key
                else AllianceTekClient.from_settings(settings)
            )

        order_payload = build_order_payload(dict(order), [dict(item) for item in items])

        try:
            response = client.create_update_order(order_payload)
        except (SupplierApiError, SupplierApiConfigError) as exc:
            with engine.begin() as conn:
                conn.execute(
                    sa.insert(supplier_attempts_table).values(
                        supplier_order_id=supplier_order_id,
                        attempt_number=next_attempt_number,
                        status="failed",
                        error_message=str(exc),
                    )
                )
            logger.warning(
                "submit_supplier_order: order %s attempt %s failed: %s",
                order["public_order_number"],
                next_attempt_number,
                exc,
            )

            error_class = classify_supplier_error(exc)
            retries_exhausted = supplier_retry_count >= len(RETRY_DELAYS_SECONDS)
            if error_class == SupplierErrorClass.TRANSIENT and not retries_exhausted:
                delay_seconds = RETRY_DELAYS_SECONDS[supplier_retry_count]
                queue.enqueue(
                    job_type="submit_supplier_order",
                    payload={"order_id": str(order_id), "supplier_retry_count": supplier_retry_count + 1},
                    delay_seconds=delay_seconds,
                )
                logger.info(
                    "submit_supplier_order: order %s scheduled for retry %s in %ss",
                    order["public_order_number"],
                    supplier_retry_count + 1,
                    delay_seconds,
                )
            else:
                reason = "retries exhausted" if retries_exhausted else f"permanent error: {exc}"
                _route_to_manual_review(engine, order=order, supplier_order_id=supplier_order_id, reason=reason)
            return

        with engine.begin() as conn:
            conn.execute(
                sa.insert(supplier_attempts_table).values(
                    supplier_order_id=supplier_order_id,
                    attempt_number=next_attempt_number,
                    status="success",
                    response_data=response if isinstance(response, dict) else {"raw": response},
                )
            )
            conn.execute(
                sa.update(supplier_orders_table)
                .where(supplier_orders_table.c.id == supplier_order_id)
                .values(status=SupplierOrderStatus.SUPPLIER_ACCEPTED, updated_at=sa.func.now())
            )
        logger.info(
            "submit_supplier_order: order %s submitted (attempt %s)",
            order["public_order_number"],
            next_attempt_number,
        )
    finally:
        if owns_client and client is not None:
            client.close()
