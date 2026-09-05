"""Fire-and-forget "a new order was placed" notification.

With manual fulfillment (David, 9/4) the person placing supplier orders
needs to hear about each order the moment it is placed — before payment
clears, so the paperwork is ready when the Venmo/Zelle transfer shows
up. When ORDER_NOTIFY_WEBHOOK_URL is set, the flat order record
(app/services/order_export.py) is POSTed there as JSON; a Zapier / Make
catch-hook that appends a row to a Google Sheet is the intended
receiver, but anything that accepts JSON works.

Runs as a FastAPI background task after the order has been committed,
so it can never delay or fail a customer's checkout: any error is
logged and dropped. There is no retry — the admin orders page and the
CSV export are the durable record; this is the nudge.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10.0


def notify_new_order(payload: dict) -> bool:
    """POST the payload to the configured webhook. Returns True when the
    receiver answered 2xx, False when unconfigured or on any failure."""
    url = get_settings().order_notify_webhook_url.strip()
    if not url:
        return False
    try:
        response = httpx.post(url, json=payload, timeout=_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        logger.warning("order notification for %s failed: %s", payload.get("order_number"), exc)
        return False
    if response.status_code >= 300:
        logger.warning(
            "order notification for %s rejected: HTTP %s", payload.get("order_number"), response.status_code
        )
        return False
    return True
