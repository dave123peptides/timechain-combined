from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from worker.alliancetek.client import AllianceTekClient
from worker.config import get_settings
from worker.db import orders_table, shipments_table, supplier_orders_table, tracking_events_table
from worker.queue.provider import QueueProvider

logger = logging.getLogger("timechain.worker.jobs.refresh_tracking")

_PROVIDER = "alliancetek"


def _get_first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return value
    return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_records(response: Any) -> list[dict[str, Any]]:
    """Best-effort extraction of a list of shipment/fulfillment records
    from an AllianceTek response whose exact shape hasn't been confirmed
    yet (only the products endpoint's `result.page/pages/total/products`
    shape has been verified against the real sandbox — see
    worker/alliancetek/client.py's docstring). Tries the wrapper shape
    the products endpoint uses plus a few plausible list keys; returns
    [] rather than guessing wrong if nothing recognizable is found."""
    if isinstance(response, list):
        return [r for r in response if isinstance(r, dict)]
    if isinstance(response, dict):
        candidate = response.get("result", response)
        if isinstance(candidate, list):
            return [r for r in candidate if isinstance(r, dict)]
        if isinstance(candidate, dict):
            for key in ("shipments", "fulfillments", "items", "records"):
                value = candidate.get(key)
                if isinstance(value, list):
                    return [r for r in value if isinstance(r, dict)]
    return []


def handle(
    payload: dict[str, Any], engine: Engine, queue: QueueProvider, *, client: Optional[AllianceTekClient] = None
) -> None:
    """job_type="refresh_tracking". payload: {"order_id": "<uuid>"}.

    Fetches fulfillments + shipments for the order's supplier_order_number
    and upserts shipments/tracking_events from whatever shipment-shaped
    records it can recognize. The response shape for these two endpoints
    hasn't been confirmed against the real AllianceTek API yet (unlike
    products) — this always logs the raw response so real shapes can be
    checked once available, and only writes rows for records it can
    actually parse (never fabricates a tracking_number or status).

    `queue` is unused here — accepted only for JobHandler signature
    parity (see worker/jobs/__init__.py); submit_supplier_order is the
    only handler that currently self-enqueues.
    """
    settings = get_settings()
    if not settings.tracking_enabled:
        logger.info(
            "refresh_tracking: TRACKING_ENABLED=false; skipping order %s without contacting AllianceTek",
            payload["order_id"],
        )
        return

    order_id = uuid.UUID(payload["order_id"])
    owns_client = client is None

    try:
        with engine.begin() as conn:
            order = conn.execute(sa.select(orders_table).where(orders_table.c.id == order_id)).mappings().one()
            supplier_order = (
                conn.execute(
                    sa.select(supplier_orders_table).where(
                        supplier_orders_table.c.order_id == order_id,
                        supplier_orders_table.c.provider == _PROVIDER,
                    )
                )
                .mappings()
                .one_or_none()
            )

        if supplier_order is None:
            logger.warning(
                "refresh_tracking: no supplier_order yet for order %s; skipping", order["public_order_number"]
            )
            return

        if client is None:
            supplier_key = supplier_order["supplier_key"]
            client = (
                AllianceTekClient.from_settings_for_supplier(settings, supplier_key)
                if supplier_key
                else AllianceTekClient.from_settings(settings)
            )

        order_number = supplier_order["supplier_order_number"]
        fulfillments = client.list_fulfillments(order_number)
        shipments = client.list_shipments(order_number)
        logger.info(
            "refresh_tracking: order %s fulfillments=%r shipments=%r", order_number, fulfillments, shipments
        )

        records = _extract_records(shipments) or _extract_records(fulfillments)
        if not records:
            logger.info(
                "refresh_tracking: order %s — no recognizable shipment records in the response; nothing written",
                order_number,
            )
            return

        with engine.begin() as conn:
            for record in records:
                tracking_number = _get_first(record, "trackingNumber", "tracking_number")
                if not tracking_number:
                    continue
                carrier = _get_first(record, "carrier", "carrierCode")
                status = _get_first(record, "status", "shipmentStatus") or "shipped"
                shipped_at = _parse_datetime(_get_first(record, "shipDate", "shippedAt", "shipped_at"))

                existing = (
                    conn.execute(
                        sa.select(shipments_table).where(
                            shipments_table.c.order_id == order_id,
                            shipments_table.c.tracking_number == tracking_number,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing is None:
                    shipment_id = uuid.uuid4()
                    conn.execute(
                        sa.insert(shipments_table).values(
                            id=shipment_id,
                            order_id=order_id,
                            carrier=carrier,
                            tracking_number=tracking_number,
                            status=status,
                            shipped_at=shipped_at,
                        )
                    )
                else:
                    shipment_id = existing["id"]
                    conn.execute(
                        sa.update(shipments_table)
                        .where(shipments_table.c.id == shipment_id)
                        .values(status=status, shipped_at=shipped_at, updated_at=sa.func.now())
                    )

                # Refresh_tracking may run repeatedly for the same order —
                # skip re-inserting an event that already exists (same
                # shipment/status/occurred_at) rather than accumulating
                # duplicate rows on every poll.
                duplicate = conn.execute(
                    sa.select(tracking_events_table.c.id).where(
                        tracking_events_table.c.shipment_id == shipment_id,
                        tracking_events_table.c.status == status,
                        tracking_events_table.c.occurred_at.is_(shipped_at)
                        if shipped_at is None
                        else tracking_events_table.c.occurred_at == shipped_at,
                    )
                ).first()
                if duplicate is None:
                    conn.execute(
                        sa.insert(tracking_events_table).values(
                            shipment_id=shipment_id,
                            status=status,
                            description=_get_first(record, "description", "statusDescription"),
                            occurred_at=shipped_at,
                            raw_data=record,
                        )
                    )
        logger.info("refresh_tracking: order %s — wrote/updated %s shipment record(s)", order_number, len(records))
    finally:
        if owns_client and client is not None:
            client.close()
