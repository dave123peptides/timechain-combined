"""Fire-and-forget order pushes to GoHighLevel (CRM + customer email).

David, 9/6: GoHighLevel is the CRM. When a customer places an order and
lands on the confirmation page, a GHL workflow (Inbound Webhook
trigger) receives the order, creates/updates the contact, and emails
them their order number plus the payment steps for the method they
chose (Venmo or Zelle copy lives in the GHL email templates; the
site's own copy is apps/web/src/lib/paymentMethods.ts). A Bitcoin
order (payment_method "bitcoin_opennode") arrives the same way; its
template should point the customer at order_url to complete payment.

David, 9/10: a second push fires once an order is PAID (OpenNode
webhook or admin Mark paid, every method) — same payload shape with
`event: "order.paid"` — to a SEPARATE inbound webhook
(GHL_ORDER_PAID_WEBHOOK_URL) so a different workflow can send the
payment-confirmed email without re-triggering the how-to-pay one. See
app/services/order_paid.py.

This module builds the customer-safe payload and POSTs it to the
workflow's inbound webhook URL. Payload rules:

- Only what the customer may see. NO product names, NO supplier SKUs
  (compliance: peptides never appear in email or transfer memos — the
  order number is the only reference), NO internal URLs.
- Flat, simple keys so GHL's inbound-webhook field mapper can bind
  them to contact fields and custom values without nesting.
- Runs as a FastAPI background task after the order commits, exactly
  like order_notify: any error is logged and dropped — it can never
  delay or fail a customer's checkout. No retry.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10.0


def ghl_payload(row: dict) -> dict | None:
    """Reduce the webhook row (order_export.order_notification_payload)
    to the customer-safe fields the GHL workflow needs. Returns None
    when the order is missing the minimum GHL needs (an email) — the
    push is skipped and logged, never raised."""
    email = (row.get("customer_email") or "").strip()
    if not email:
        logger.info("GHL push skipped for %s: no customer email", row.get("order_number"))
        return None
    name = (row.get("customer_name") or "").strip()
    first_name, _, last_name = name.partition(" ")
    return {
        "email": email,
        "first_name": first_name,
        "last_name": last_name.strip(),
        "name": name,
        "phone": (row.get("customer_phone") or "").strip(),
        "order_number": row.get("order_number") or "",
        "payment_method": row.get("payment_method") or "",
        "total": row.get("total") or "",
        "currency": (row.get("currency") or "usd").upper(),
        "order_url": row.get("order_url") or "",
        # Why this push is happening: "order.created" (placed, unpaid) or
        # "order.paid" (payment confirmed). Lets a workflow branch even
        # if both events ever land on the same URL.
        "event": row.get("event") or "order.created",
        "order_status": row.get("status") or "",
        # Human labels so the GHL email can say "Bitcoin" without a
        # branch per method, plus the page the customer pays on (for
        # Bitcoin the QR lives there; for Venmo/Zelle the instructions).
        "payment_method_label": _METHOD_LABELS.get(row.get("payment_method") or "", row.get("payment_method") or ""),
        "pay_url": row.get("order_url") or "",
    }


_METHOD_LABELS = {
    "venmo": "Venmo",
    "zelle": "Zelle",
    "paypal": "PayPal",
    "whop": "Card / Apple Pay",
    "bitcoin_opennode": "Bitcoin",
    "crypto": "Bitcoin",
    "ach": "ACH",
}


def push_order_to_ghl(payload: dict, *, url: str | None = None) -> bool:
    """POST the payload to a GHL workflow webhook — the new-order URL
    (GHL_ORDER_WEBHOOK_URL) by default, or the explicit `url` a caller
    passes (the paid fan-out passes GHL_ORDER_PAID_WEBHOOK_URL). Returns
    True on 2xx, False when unconfigured or on any failure."""
    url = (url if url is not None else get_settings().ghl_order_webhook_url).strip()
    if not url:
        return False
    try:
        response = httpx.post(url, json=payload, timeout=_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        logger.warning("GHL push for %s failed: %s", payload.get("order_number"), exc)
        return False
    if response.status_code >= 300:
        logger.warning(
            "GHL push for %s rejected: HTTP %s", payload.get("order_number"), response.status_code
        )
        return False
    return True
