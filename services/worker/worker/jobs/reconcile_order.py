from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from worker.alliancetek.client import AllianceTekClient
from worker.config import get_settings
from worker.db import orders_table, supplier_attempts_table, supplier_orders_table
from worker.queue.provider import QueueProvider

logger = logging.getLogger("timechain.worker.jobs.reconcile_order")

_PROVIDER = "alliancetek"


def _extract_status(response: Any) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    result = response.get("result", response)
    if not isinstance(result, dict):
        return None
    for key in ("orderStatus", "status"):
        value = result.get(key)
        if isinstance(value, str):
            return value
    return None


def handle(
    payload: dict[str, Any], engine: Engine, queue: QueueProvider, *, client: Optional[AllianceTekClient] = None
) -> None:
    """job_type="reconcile_order". payload: {"order_id": "<uuid>"}.

    Fetches AllianceTek's own view of the order and compares it to our
    locally recorded SupplierOrder.status. On drift, this only logs and
    records a SupplierAttempt for audit — it never silently overwrites
    the local status. Same "requires deliberate action, not silent
    auto-correction" posture as mapping drift reconciliation on the api
    side (see app/services/mapping_status.py).

    `queue` is unused here — accepted only for JobHandler signature
    parity (see worker/jobs/__init__.py).
    """
    settings = get_settings()
    if not settings.tracking_enabled:
        logger.info(
            "reconcile_order: TRACKING_ENABLED=false; skipping order %s without contacting AllianceTek",
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
                "reconcile_order: no supplier_order yet for order %s; skipping", order["public_order_number"]
            )
            return

        if client is None:
            supplier_key = supplier_order["supplier_key"]
            client = (
                AllianceTekClient.from_settings_for_supplier(settings, supplier_key)
                if supplier_key
                else AllianceTekClient.from_settings(settings)
            )

        remote = client.get_order(supplier_order["supplier_order_number"])
        remote_status = _extract_status(remote)
        logger.info(
            "reconcile_order: order %s local_status=%s remote_status=%s",
            supplier_order["supplier_order_number"],
            supplier_order["status"],
            remote_status,
        )

        if remote_status is None or remote_status == supplier_order["status"]:
            return

        logger.warning(
            "reconcile_order: order %s drifted — local=%s remote=%s; recording for audit, not auto-correcting",
            supplier_order["supplier_order_number"],
            supplier_order["status"],
            remote_status,
        )
        with engine.begin() as conn:
            next_attempt_number = conn.execute(
                sa.select(
                    sa.func.coalesce(sa.func.max(supplier_attempts_table.c.attempt_number), 0) + 1
                ).where(supplier_attempts_table.c.supplier_order_id == supplier_order["id"])
            ).scalar_one()
            conn.execute(
                sa.insert(supplier_attempts_table).values(
                    supplier_order_id=supplier_order["id"],
                    attempt_number=next_attempt_number,
                    status="reconciled",
                    response_data=remote if isinstance(remote, dict) else {"raw": remote},
                )
            )
    finally:
        if owns_client and client is not None:
            client.close()
