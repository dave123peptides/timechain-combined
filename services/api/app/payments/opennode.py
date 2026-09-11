"""OpenNode Bitcoin payment provider (Lightning + on-chain, USD-priced).

Implements the PaymentProvider protocol from app/payments/base.py so it
drops into app/payments/registry.py and the existing webhook route
without touching the order-status state machine (see
app/services/payments.py — mark_order_paid / mark_order_payment_failed
remain the only transition path, exactly as base.py's docstring
promises). Registered as "bitcoin_opennode" (David, 2026-09-10); the
dormant Speed provider keeps the "crypto" key for historical rows.

OpenNode API facts this module relies on (developers.opennode.com,
cross-checked against the official opennode-node SDK source, 2026-09-10):

- Base URL: https://api.opennode.com (live) or https://dev-api.opennode.com
  (dev/testnet) — Settings.opennode_environment picks one.
- Auth: `Authorization: *** key>` — the bare key, no "Bearer". Keys come
  from Dashboard → Developers → API keys; use one with the invoices
  permission only.
- POST /v1/charges creates a charge. With `currency: "USD"`, `amount` is
  in MAJOR units (dollars, e.g. 129.50 — never cents) and OpenNode quotes
  the BTC amount at creation. `ttl` is in MINUTES (10..4320). Response
  (HTTP 200/201): {"data": {"id", "status": "unpaid",
  "hosted_checkout_url", ...}}. The hosted page
  (checkout.opennode.com/{id}) offers Lightning and on-chain.
- Correlation: we store the charge `id` as Payment.provider_payment_id at
  creation time and also send our public order number as `order_id`.
  Webhooks carry both; handle_event resolves the Payment row by the
  charge id and cross-checks order_id.
- Webhooks: OpenNode POSTs to `callback_url` as
  application/x-www-form-urlencoded (NOT JSON) with id, status,
  order_id, price (sats), fee, description, callback_url, success_url,
  auto_settle and hashed_order (+ missing_amt / overpaid_by /
  transactions / address for on-chain). There is no event id and no
  timestamp or signature header.
- Signature: `hashed_order` = hex(HMAC-SHA256(key = the API key that
  created the charge, msg = charge id)). There is NO separate webhook
  secret. Because the HMAC covers only the charge id (not the status),
  a "paid" webhook is re-confirmed with GET /v2/charge/{id} before the
  order is marked paid.
- Statuses that fire webhooks: on-chain processing / paid / underpaid /
  expired / refunded / failed; Lightning paid / expired.
- Dashboard → Developers → Webhook simulator sends genuinely signed
  webhooks for any status without a real payment.

Fail-closed behaviour: with OPENNODE_API_KEY blank, or
OPENNODE_CALLBACK_URL blank / not https, charge creation raises
OpenNodeNotConfigured, which the checkout flow turns into "order
created, no Bitcoin checkout yet" (the order page's Pay button reports
Bitcoin as unavailable) rather than a broken checkout. With the key
blank, every webhook is rejected 400.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.order_status import OrderStatus
from app.models.orders import Order, OrderEvent
from app.models.payments import Payment, PaymentEvent
from app.payments.base import PaymentInstructions, VerifiedEvent
from app.services import payments as payment_services

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_SECONDS = 20.0
# How long a charge stays payable. OpenNode's ttl is in minutes and
# defaults to 24 h; one hour (same as the Speed provider) is long enough
# to fetch a wallet and short enough that the quoted BTC amount stays
# honest. An expired charge leaves the order pending and the order
# page's Pay button mints a new one.
_CHARGE_TTL_MINUTES = 60
# Dollar tolerance for the informational fiat cross-check on "paid".
_AMOUNT_TOLERANCE = 0.01
_API_BASES = {
    "live": "https://api.opennode.com",
    "dev": "https://dev-api.opennode.com",
}
_HOSTED_CHECKOUT_HOSTS = {
    "live": "checkout.opennode.com",
    "dev": "checkout.dev.opennode.com",
}
# Webhook statuses that change the Payment row's status (never the
# Order's — only mark_order_paid moves an order). "paid" is handled
# separately; "refunded" and anything new are recorded only.
_PAYMENT_STATUS_FOR = {
    "processing": "processing",
    "underpaid": "underpaid",
    "expired": "expired",
    "failed": "failed",
}


class OpenNodeError(RuntimeError):
    """Any OpenNode-side failure (HTTP error, unexpected payload, bad
    signature). Checkout catches this and degrades gracefully — the
    order still exists, payment instructions just aren't attached."""


class OpenNodeNotConfigured(OpenNodeError):
    """OPENNODE_API_KEY is blank, or OPENNODE_CALLBACK_URL is not a
    public https URL. Raised lazily at call time, never at import or
    registration time, so the app boots fine without keys."""


def _client() -> httpx.Client:
    """Fresh client per call — charge creation happens at most once per
    order and the paid re-check at most once per delivery, so the
    simplicity beats a shared connection pool. Tests monkeypatch this."""
    return httpx.Client(timeout=_HTTP_TIMEOUT_SECONDS)


def _require_api_key() -> str:
    key = get_settings().opennode_api_key.strip()
    if not key:
        raise OpenNodeNotConfigured("OPENNODE_API_KEY is not configured.")
    return key


def _environment() -> str:
    env = get_settings().opennode_environment.strip().lower()
    if env not in _API_BASES:
        raise OpenNodeError(f"OPENNODE_ENVIRONMENT must be one of {sorted(_API_BASES)}, not {env!r}.")
    return env


def _api_base() -> str:
    return _API_BASES[_environment()]


def _auth_headers(api_key: str) -> dict[str, str]:
    # The bare key — no "Bearer" prefix — exactly as OpenNode's own SDK
    # sends it.
    return {"Authorization": api_key, "Content-Type": "application/json"}


def compute_hashed_order(api_key: str, charge_id: str) -> str:
    """The hex HMAC-SHA256 a valid webhook's `hashed_order` must carry:
    keyed with the API key, over the charge id. Exposed at module level
    purely so tests can sign fixtures with the same code path production
    verifies with."""
    return hmac.new(api_key.encode("utf-8"), charge_id.encode("utf-8"), hashlib.sha256).hexdigest()


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def parse_webhook_body(headers: dict[str, str], raw_body: bytes) -> dict[str, str]:
    """OpenNode delivers webhooks form-encoded; accept JSON too (the
    same fields, optionally wrapped in `data`) so a simulator or a future
    format change still verifies. Always returns a flat dict of strings,
    which is what WebhookEvent.payload (JSONB) stores."""
    if not raw_body:
        raise OpenNodeError("Empty webhook body.")
    norm = {k.lower(): v for k, v in headers.items()}
    content_type = norm.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = json.loads(raw_body)
        except ValueError as exc:
            raise OpenNodeError(f"Unparseable JSON webhook body: {exc}") from exc
        if isinstance(body, dict) and "id" not in body and isinstance(body.get("data"), dict):
            body = body["data"]
        if not isinstance(body, dict):
            raise OpenNodeError("JSON webhook body is not an object.")
        return {str(k): _stringify(v) for k, v in body.items()}
    try:
        text = raw_body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OpenNodeError("Webhook body is not UTF-8.") from exc
    parsed = parse_qs(text, keep_blank_values=True)
    if not parsed:
        raise OpenNodeError("Webhook body has no form fields.")
    return {key: values[-1] for key, values in parsed.items()}


def _charge_expiry(data: dict[str, Any]) -> str | None:
    """ISO-8601 UTC expiry for a freshly created charge: created_at
    (unix seconds) + ttl (minutes), which is what the hosted page counts
    down from. None when either is missing or malformed."""
    try:
        created = int(data.get("created_at"))
        ttl_minutes = int(data.get("ttl") or _CHARGE_TTL_MINUTES)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(created + ttl_minutes * 60, tz=timezone.utc).isoformat()


def fetch_charge(charge_id: str) -> dict[str, Any]:
    """GET the charge from OpenNode — the source of truth for its status.
    The docs name the path /v2/charge/{id}; the official SDK calls
    /v2/charges/{id}; try the documented one first and fall back on 404.
    Raises OpenNodeError on any failure so the caller can refuse to act."""
    api_key = _require_api_key()
    base = _api_base()
    try:
        with _client() as client:
            response = client.get(f"{base}/v2/charge/{charge_id}", headers=_auth_headers(api_key))
            if response.status_code == 404:
                response = client.get(f"{base}/v2/charges/{charge_id}", headers=_auth_headers(api_key))
    except httpx.HTTPError as exc:
        raise OpenNodeError(f"OpenNode charge lookup for {charge_id} failed: {exc}") from exc
    if response.status_code != 200:
        raise OpenNodeError(
            f"OpenNode charge lookup for {charge_id} failed ({response.status_code}): {response.text[:300]}"
        )
    try:
        data = response.json().get("data")
    except ValueError as exc:
        raise OpenNodeError(f"OpenNode charge lookup for {charge_id} returned non-JSON.") from exc
    if not isinstance(data, dict):
        raise OpenNodeError(f"OpenNode charge lookup for {charge_id} returned no charge object.")
    return data


class OpenNodeProvider:
    provider_key = "bitcoin_opennode"

    # -- charge creation -------------------------------------------------

    def create_payment_instructions(self, order: Order) -> PaymentInstructions:
        """Create an OpenNode charge for the order's USD total and return
        what the checkout flow needs to send the customer to the hosted
        payment page (Lightning / on-chain / QR — their choice)."""
        api_key = _require_api_key()  # raises OpenNodeNotConfigured if no key
        settings = get_settings()
        callback_url = settings.opennode_callback_url.strip()
        if not callback_url.startswith("https://"):
            # Without a callback the charge could never confirm the
            # order on its own; refusing here keeps "Bitcoin is on" and
            # "Bitcoin works" the same thing.
            raise OpenNodeNotConfigured("OPENNODE_CALLBACK_URL must be a public https URL.")
        environment = _environment()

        payload: dict[str, Any] = {
            # Major units (dollars), not cents; two decimals so the
            # hosted page and our ledger agree.
            "amount": round(order.total_cents / 100, 2),
            "currency": "USD",
            # Shown in the payer's wallet — the same place a Venmo memo
            # goes, so per the store's memo rule it never names peptides.
            "description": f"Timechain Order {order.public_order_number}",
            "order_id": order.public_order_number,
            "customer_email": order.customer_email,
            "ttl": _CHARGE_TTL_MINUTES,
            "callback_url": callback_url,
        }
        if order.customer_name:
            payload["customer_name"] = order.customer_name
        # Redirect back is only valid once the storefront has a public
        # https URL; until then the hosted page shows OpenNode's own
        # success screen and the paid webhook still flips the order.
        site = settings.public_site_url.strip().rstrip("/")
        if site.startswith("https://"):
            payload["success_url"] = f"{site}/order/{order.access_token}"

        try:
            with _client() as client:
                response = client.post(
                    f"{_API_BASES[environment]}/v1/charges",
                    headers=_auth_headers(api_key),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise OpenNodeError(f"OpenNode charge creation failed: {exc}") from exc
        if response.status_code not in (200, 201):
            raise OpenNodeError(
                f"OpenNode charge creation failed ({response.status_code}): {response.text[:300]}"
            )
        try:
            data = response.json().get("data")
        except ValueError as exc:
            raise OpenNodeError("OpenNode charge response is not JSON.") from exc
        charge_id = data.get("id") if isinstance(data, dict) else None
        if not charge_id:
            raise OpenNodeError(f"OpenNode response missing the charge id: {str(data)[:300]}")
        checkout_url = data.get("hosted_checkout_url") or f"https://{_HOSTED_CHECKOUT_HOSTS[environment]}/{charge_id}"

        # Everything the order page needs to show the payment itself
        # (David, 9/11: the QR and "open in wallet" live on our page; the
        # customer is never bounced to OpenNode). Stored on the Payment
        # row as provider_data so every later visit can draw it again.
        lightning = data.get("lightning_invoice") if isinstance(data.get("lightning_invoice"), dict) else {}
        chain = data.get("chain_invoice") if isinstance(data.get("chain_invoice"), dict) else {}
        expires_at = _charge_expiry(data)

        return PaymentInstructions(
            provider=self.provider_key,
            summary="Pay with Bitcoin (Lightning or on-chain)",
            details={
                "provider_payment_id": charge_id,
                "checkout_url": checkout_url,
                "usd_total_cents": order.total_cents,
                "expires_in_seconds": _CHARGE_TTL_MINUTES * 60,
                "expires_at": expires_at,
                "amount_sats": data.get("amount"),
                "lightning_invoice": lightning.get("payreq") or None,
                "chain_address": chain.get("address") or data.get("address") or None,
                "bitcoin_uri": data.get("uri") or None,
            },
        )

    # -- webhook verification --------------------------------------------

    def verify_webhook(self, headers: dict[str, str], raw_body: bytes) -> VerifiedEvent:
        """Check `hashed_order` against the HMAC of the charge id and
        parse the (form-encoded) body. Any failure raises —
        app/api/webhooks.py turns that into a 400 and never calls
        handle_event."""
        api_key = _require_api_key()  # blank key → every webhook rejected
        fields = parse_webhook_body(headers, raw_body)
        charge_id = (fields.get("id") or "").strip()
        status = (fields.get("status") or "").strip().lower()
        provided = (fields.get("hashed_order") or "").strip().lower()
        if not charge_id or not status or not provided:
            raise OpenNodeError("Missing id / status / hashed_order field.")
        expected = compute_hashed_order(api_key, charge_id)
        if not hmac.compare_digest(expected, provided):
            raise OpenNodeError("hashed_order does not match the charge id.")
        # external_id = charge id + status: OpenNode has no event id, and
        # a retried delivery of the same status must dedupe at the route
        # (WebhookEvent UNIQUE(source, external_id)) while the next
        # status for the same charge (processing → paid) still processes.
        return VerifiedEvent(
            external_id=f"{charge_id}:{status}",
            event_type=f"charge.{status}",
            order_id=(fields.get("order_id") or "").strip() or None,
            raw=fields,
        )

    # -- verified event handling ------------------------------------------

    def handle_event(self, session: Session, event: VerifiedEvent) -> uuid.UUID | None:
        """Map a verified charge event onto the existing order-state
        transitions. Does not commit — app/api/webhooks.py owns the
        transaction boundary. Returns the order id when this event
        marked the order paid, else None."""
        fields = event.raw
        charge_id = str(fields.get("id") or "")
        status = str(fields.get("status") or "").lower()

        payment = session.execute(
            select(Payment).where(Payment.provider_payment_id == charge_id)
        ).scalar_one_or_none()
        if payment is None:
            # A charge we didn't create (simulator, another account) or a
            # stale delivery for a row that was cleaned up.
            logger.warning("OpenNode webhook for unknown charge %s (%s) — ignored.", charge_id, status)
            return None
        order = session.get(Order, payment.order_id)
        if order is None:
            logger.error("OpenNode charge %s has a Payment row but no order — ignored.", charge_id)
            return None
        if event.order_id and event.order_id != order.public_order_number:
            logger.error(
                "OpenNode charge %s carries order_id %r but belongs to order %s — refused.",
                charge_id,
                event.order_id,
                order.public_order_number,
            )
            return None

        if status == "paid":
            return self._handle_paid(session, order, payment, charge_id, event)

        if payment.status == "succeeded":
            # A late processing/expired delivery for a charge that already
            # paid the order must never downgrade the row.
            self._record(session, payment, event, fields)
            logger.info("OpenNode charge %s event %s after payment succeeded — recorded only.", charge_id, status)
        elif status in _PAYMENT_STATUS_FOR:
            payment.status = _PAYMENT_STATUS_FOR[status]
            session.add(payment)
            self._record(session, payment, event, fields)
            if status == "underpaid":
                # Surfaced in admin history; David accepts or refunds the
                # underpayment in OpenNode's dashboard and, if accepted,
                # marks the order paid there. The order stays pending.
                session.add(
                    OrderEvent(
                        order_id=order.id,
                        event_type="payment_underpaid",
                        data={"charge_id": charge_id, "missing_amt_sats": fields.get("missing_amt")},
                    )
                )
            logger.info("OpenNode charge %s is %s — order %s stays pending.", charge_id, status, order.public_order_number)
        else:
            # refunded / anything OpenNode adds later: record, no transition.
            self._record(session, payment, event, fields)
            logger.info("OpenNode charge %s event %s — recorded, no state transition.", charge_id, status)
        # Flush like mark_order_paid does, so the row is consistent for
        # anything that reads it in this transaction; the route commits.
        session.flush()
        return None

    def _handle_paid(
        self, session: Session, order: Order, payment: Payment, charge_id: str, event: VerifiedEvent
    ) -> uuid.UUID | None:
        if order.status != OrderStatus.PAYMENT_PENDING:
            logger.info(
                "OpenNode paid webhook for order %s which is already %s — no-op.",
                order.public_order_number,
                order.status,
            )
            return None
        # Defense in depth: hashed_order proves OpenNode created this
        # charge but says nothing about the status field, so ask OpenNode
        # before moving money-state. Raising (rather than returning) on a
        # mismatch or a network failure makes the route answer 500 with
        # nothing committed, so the same event can be redelivered and
        # processed once OpenNode really reports it paid.
        charge = fetch_charge(charge_id)
        api_status = str(charge.get("status") or "").lower()
        if api_status != "paid":
            raise OpenNodeError(
                f"OpenNode reports charge {charge_id} as {api_status!r}, not paid — "
                f"refusing to mark order {order.public_order_number} paid."
            )
        self._check_fiat_amount(session, order, payment, charge_id, charge)
        try:
            payment_services.mark_order_paid(
                session,
                order_id=order.id,
                provider=self.provider_key,
                provider_payment_id=charge_id,
                source="opennode:webhook",
                payment_id=payment.id,
            )
        except payment_services.PaymentActionError as exc:
            logger.info("OpenNode paid webhook for %s is a no-op: %s", order.public_order_number, exc)
            return None
        logger.info("Order %s marked paid from OpenNode charge %s.", order.public_order_number, charge_id)
        return order.id

    @staticmethod
    def _check_fiat_amount(
        session: Session, order: Order, payment: Payment, charge_id: str, charge: dict[str, Any]
    ) -> None:
        """Informational only in v1: the charge was minted by us for this
        exact USD total, and OpenNode's own docs don't say whether
        source_fiat_value is dollars or cents, so a disagreement is
        logged and recorded on the order rather than blocking a real
        payment. Tighten once a live charge has shown the unit."""
        raw = charge.get("source_fiat_value", charge.get("fiat_value"))
        if raw in (None, ""):
            return
        try:
            fiat = float(raw)
        except (TypeError, ValueError):
            return
        expected = round(payment.amount_cents / 100, 2)
        if abs(fiat - expected) <= _AMOUNT_TOLERANCE or abs(fiat / 100 - expected) <= _AMOUNT_TOLERANCE:
            return
        logger.warning(
            "OpenNode charge %s reports fiat value %s but order %s expects %.2f USD — recorded, still marking paid.",
            charge_id,
            raw,
            order.public_order_number,
            expected,
        )
        session.add(
            OrderEvent(
                order_id=order.id,
                event_type="payment_amount_mismatch",
                data={"charge_id": charge_id, "charge_fiat_value": str(raw), "expected_usd": expected},
            )
        )

    @staticmethod
    def _record(session: Session, payment: Payment, event: VerifiedEvent, fields: dict[str, Any]) -> None:
        session.add(
            PaymentEvent(
                payment_id=payment.id,
                provider_event_id=event.external_id,
                event_type=event.event_type,
                data={
                    "status": fields.get("status"),
                    "price_sats": fields.get("price"),
                    "missing_amt": fields.get("missing_amt"),
                    "overpaid_by": fields.get("overpaid_by"),
                },
            )
        )
