"""Whop hosted checkout — credit / debit card and Apple Pay.

Implements the PaymentProvider protocol from app/payments/base.py so it
drops into app/payments/registry.py and the existing webhook route
without touching the order-status state machine (see
app/services/payments.py — mark_order_paid / mark_order_payment_failed
remain the only transition path, exactly as base.py's docstring
promises). Registered as "whop" (David, 2026-09-14) next to the
OpenNode provider, whose structure this module mirrors.

Whop API facts this module relies on (docs.whop.com plus the official
whopsdk-python / whopsdk-typescript source, checked 2026-09-14):

- Base URL: https://api.whop.com/api/v1 (live) or
  https://sandbox-api.whop.com/api/v1 (sandbox: cards only, no Apple
  Pay) — Settings.whop_environment picks one.
- Auth: `Authorization: Bearer <account API key>`. Request and response
  shapes are selected by the `Api-Version-Date` header; without it the
  key's stored pin applies. We pin explicitly
  (Settings.whop_api_version_date) so the shapes are deterministic.
- POST /checkout_configurations creates a hosted checkout for an inline
  one-time plan: {"mode": "payment", "plan": {"title", "plan_type":
  "one_time", "initial_price": <dollars, MAJOR units>, "currency":
  "usd"}, "metadata": {...}, "redirect_url": "<where the buyer lands
  after paying>"}. Response (200/201): {"id": "ch_…", "purchase_url":
  "https://whop.com/checkout/…", ...}. `metadata` is copied onto the
  resulting payment, which is how the webhook finds our order.
  plan.title is capped at 30 characters. `account_id` ("biz_…") is
  optional with an account key and sent only when configured.
- Webhooks follow the Standard Webhooks spec: headers `webhook-id`
  ("msg_…"), `webhook-timestamp` (unix seconds) and `webhook-signature`
  ("v1,<base64>", possibly several space-separated values). Signed
  string: "{webhook-id}.{webhook-timestamp}.{raw body}", HMAC-SHA256
  keyed with the RAW UTF-8 bytes of the whole signing secret exactly as
  Whop shows it — the "ws_…" prefix included, nothing stripped, nothing
  base64-decoded. (The official SDKs base64-encode the secret before
  handing it to the standardwebhooks library, which decodes it again.)
  Deliveries are retried with the same webhook-id for ~3 days; Whop
  expects a 2xx within 5 seconds.
- Envelope: {"id": "msg_…", "type": "payment.succeeded", "data":
  <payment object>, "api_version_date": ..., ...}. Payment object:
  "id" ("pay_…"), "status" (draft | open | authorized | paid | pending |
  uncollectible | unresolved | void — some docs samples show
  "succeeded"), "substatus" ("succeeded", "failed", "refunded", ...),
  "total" (the plan price after discounts plus any tax Whop added,
  excluding buyer fees — the number that must match our order total),
  "subtotal", "usd_total", "amount_after_fees" (net of Whop's fees —
  never our total), "currency", "metadata", "checkout_configuration_id",
  "card_brand", "card_last4", "payment_method_type", "paid_at". Money
  fields are plain dollar numbers on older API pins and
  {"amount": "10.00", "currency": "usd", "decimals": 2} objects on pins
  from 2026-09-02-1; a webhook's shape follows the WEBHOOK's own pin
  (set in the dashboard), so parse_money accepts number, numeric string
  and object alike.
- GET /payments/{id} returns one payment — the source of truth we ask
  before moving money-state on a "payment.succeeded" delivery.

Compliance (David): the only things Whop ever sees are the store's
order number and the amount — plan.title is "Order PEN-…" and metadata
carries just order_number. No product names, no customer names, no
emails.

Fail-closed behaviour: with WHOP_API_KEY blank, or PUBLIC_SITE_URL
blank / not http(s), checkout creation raises WhopNotConfigured, which
the checkout flow turns into "order created, no Pay Now link yet" (the
order page offers Try again) rather than a broken checkout. With
WHOP_WEBHOOK_SECRET blank every webhook is rejected 400. With the key
blank, a paid webhook cannot be re-checked and answers 500 with nothing
committed until the key is set — Whop keeps retrying.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

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

# Whop expects a 2xx within 5 s and retries otherwise. The paid re-check
# is the only call on the webhook path, so keep it short; a slow answer
# just means a retry that dedupes at the route once our commit lands.
_HTTP_TIMEOUT_SECONDS = 10.0
# Standard Webhooks replay window: a delivery whose timestamp is further
# than this from now, in either direction, is refused.
_WEBHOOK_TOLERANCE_SECONDS = 300
_PLAN_TITLE_MAX = 30
_API_BASES = {
    "live": "https://api.whop.com/api/v1",
    "sandbox": "https://sandbox-api.whop.com/api/v1",
}
_PAID_EVENT = "payment.succeeded"
_PAID_STATUSES = {"paid", "succeeded"}
_PAID_SUBSTATUSES = {"succeeded"}
# Events that change the Payment row's status (never the Order's — only
# mark_order_paid moves an order). payment.succeeded is handled
# separately; refunds, disputes and anything new are recorded only.
_PAYMENT_STATUS_FOR = {
    "payment.failed": "failed",
    "payment.canceled": "failed",
    "payment.pending": "processing",
    "payment.authorized": "processing",
}


class WhopError(RuntimeError):
    """Any Whop-side failure (HTTP error, unexpected payload, bad
    signature, an amount we cannot read). Checkout catches this and
    degrades gracefully — the order still exists, the Pay Now link just
    isn't attached."""


class WhopNotConfigured(WhopError):
    """WHOP_API_KEY / WHOP_WEBHOOK_SECRET is blank, or PUBLIC_SITE_URL is
    not an http(s) URL. Raised lazily at call time, never at import or
    registration time, so the app boots fine without keys."""


def _client() -> httpx.Client:
    """Fresh client per call — checkout creation happens at most once per
    order and the paid re-check at most once per delivery. Tests
    monkeypatch this."""
    return httpx.Client(timeout=_HTTP_TIMEOUT_SECONDS)


def _require_api_key() -> str:
    key = get_settings().whop_api_key.strip()
    if not key:
        raise WhopNotConfigured("WHOP_API_KEY is not configured.")
    return key


def _require_webhook_secret() -> str:
    secret = get_settings().whop_webhook_secret.strip()
    if not secret:
        raise WhopNotConfigured("WHOP_WEBHOOK_SECRET is not configured.")
    return secret


def _environment() -> str:
    env = get_settings().whop_environment.strip().lower()
    if env not in _API_BASES:
        raise WhopError(f"WHOP_ENVIRONMENT must be one of {sorted(_API_BASES)}, not {env!r}.")
    return env


def _api_base() -> str:
    return _API_BASES[_environment()]


def _headers(api_key: str) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    # Pin the API version so request/response shapes never drift under
    # us; blank means "whatever pin the key carries".
    pin = get_settings().whop_api_version_date.strip()
    if pin:
        headers["Api-Version-Date"] = pin
    return headers


def _redirect_url(order: Order) -> str:
    """Where Whop sends the customer after paying: their order page.
    Without a usable PUBLIC_SITE_URL the customer would be stranded on
    Whop's receipt, so refuse to create the checkout at all (the order
    still exists; the order page offers Try again once configured).
    http is allowed for local development."""
    site = get_settings().public_site_url.strip().rstrip("/")
    if not (site.startswith("https://") or site.startswith("http://")):
        raise WhopNotConfigured(
            "PUBLIC_SITE_URL must be an http(s) URL so Whop can send the customer back to the order page."
        )
    return f"{site}/order/{order.access_token}"


def compute_signature(secret: str, msg_id: str, timestamp: int | str, raw_body: bytes) -> str:
    """The `v1,<base64>` value a valid webhook's webhook-signature header
    carries: HMAC-SHA256 keyed with the secret's raw UTF-8 bytes (prefix
    and all), over "{id}.{timestamp}.{raw body}". Exposed at module level
    purely so tests can sign fixtures with the same code path production
    verifies with."""
    signed = f"{msg_id}.{int(timestamp)}.".encode("utf-8") + raw_body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode("ascii")


def parse_money(value: Any) -> float | None:
    """Dollars from any shape Whop uses for a money field: a number, a
    numeric string, or a Money object {"amount": "10.00", ...}. None for
    anything unreadable — callers treat that as "do not trust"."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dict):
        return parse_money(value.get("amount"))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = Decimal(text)
        except (InvalidOperation, ValueError):
            return None
        if not parsed.is_finite():
            return None
        return float(parsed)
    return None


def _to_cents(dollars: float) -> int:
    return int((Decimal(str(dollars)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _reads_paid(payment_obj: dict[str, Any]) -> bool:
    status = str(payment_obj.get("status") or "").lower()
    substatus = str(payment_obj.get("substatus") or "").lower()
    return status in _PAID_STATUSES or substatus in _PAID_SUBSTATUSES


def _amount_fields(payment_obj: dict[str, Any]) -> tuple[float | None, str | None]:
    """(dollars, currency) of what the buyer paid: the first readable of
    total / usd_total / subtotal. The currency comes from the Money
    object when there is one, else the payment's currency; usd_total is
    USD by definition."""
    for key in ("total", "usd_total", "subtotal"):
        raw = payment_obj.get(key)
        dollars = parse_money(raw)
        if dollars is None:
            continue
        currency: str | None = None
        if isinstance(raw, dict) and raw.get("currency"):
            currency = str(raw["currency"]).lower()
        elif key == "usd_total":
            currency = "usd"
        elif payment_obj.get("currency"):
            currency = str(payment_obj["currency"]).lower()
        return dollars, currency
    return None, None


def _order_number_from(data: dict[str, Any]) -> str | None:
    """Our public order number, from the metadata the checkout
    configuration copied onto the payment (or, on shapes that nest it,
    from the embedded checkout configuration)."""
    for holder in (data, data.get("checkout_configuration")):
        if not isinstance(holder, dict):
            continue
        metadata = holder.get("metadata")
        if isinstance(metadata, dict):
            number = str(metadata.get("order_number") or "").strip()
            if number:
                return number
    return None


def _unwrap(body: Any) -> Any:
    """Accept a bare object or one wrapped in {"data": {...}}."""
    if isinstance(body, dict) and "id" not in body and isinstance(body.get("data"), dict):
        return body["data"]
    return body


def _scalar(value: Any) -> Any:
    """JSON-safe scalar for the event log (JSONB): never a nested object."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)[:200]


def fetch_payment(payment_id: str) -> dict[str, Any]:
    """GET the payment from Whop — the source of truth for its status and
    amount. Raises WhopError on any failure so the caller can refuse to
    act (the route then answers 500 with nothing committed)."""
    api_key = _require_api_key()
    base = _api_base()
    try:
        with _client() as client:
            response = client.get(f"{base}/payments/{payment_id}", headers=_headers(api_key))
    except httpx.HTTPError as exc:
        raise WhopError(f"Whop payment lookup for {payment_id} failed: {exc}") from exc
    if response.status_code != 200:
        raise WhopError(
            f"Whop payment lookup for {payment_id} failed ({response.status_code}): {response.text[:300]}"
        )
    try:
        data = _unwrap(response.json())
    except ValueError as exc:
        raise WhopError(f"Whop payment lookup for {payment_id} returned non-JSON.") from exc
    if not isinstance(data, dict) or not data.get("id"):
        raise WhopError(f"Whop payment lookup for {payment_id} returned no payment object.")
    return data


class WhopProvider:
    provider_key = "whop"

    # -- checkout creation ---------------------------------------------------

    def create_payment_instructions(self, order: Order) -> PaymentInstructions:
        """Create a Whop checkout configuration for the order's USD total
        and return what the order page needs: the hosted purchase_url
        behind its Pay Now button."""
        api_key = _require_api_key()  # raises WhopNotConfigured if no key
        redirect_url = _redirect_url(order)  # ... or no usable site URL
        base = _api_base()
        settings = get_settings()

        payload: dict[str, Any] = {
            "mode": "payment",
            "plan": {
                # Shown on Whop's page and receipt — the same place a
                # Venmo memo goes, so per the store's memo rule it
                # names only the order.
                "title": f"Order {order.public_order_number}"[:_PLAN_TITLE_MAX],
                "plan_type": "one_time",
                # Major units (dollars), not cents; two decimals so the
                # hosted page and our ledger agree.
                "initial_price": round(order.total_cents / 100, 2),
                "currency": "usd",
            },
            # Copied onto the payment; the webhook hands it back.
            "metadata": {"order_number": order.public_order_number},
            "redirect_url": redirect_url,
        }
        account_id = settings.whop_account_id.strip()
        if account_id:
            payload["account_id"] = account_id
        # Deliberately NO Idempotency-Key: retry-payment mints a second
        # Payment row for the same order, and provider_payment_id is
        # UNIQUE, so an idempotent replay returning the same ch_ id would
        # collide. An orphaned unpaid configuration is harmless.

        try:
            with _client() as client:
                response = client.post(
                    f"{base}/checkout_configurations",
                    headers=_headers(api_key),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise WhopError(f"Whop checkout creation failed: {exc}") from exc
        if response.status_code not in (200, 201):
            raise WhopError(
                f"Whop checkout creation failed ({response.status_code}): {response.text[:300]}"
            )
        try:
            data = _unwrap(response.json())
        except ValueError as exc:
            raise WhopError("Whop checkout response is not JSON.") from exc
        if not isinstance(data, dict):
            raise WhopError(f"Whop checkout response is not an object: {str(data)[:300]}")
        config_id = str(data.get("id") or "")
        purchase_url = str(data.get("purchase_url") or "")
        if not config_id:
            raise WhopError(f"Whop response missing the checkout configuration id: {str(data)[:300]}")
        if not purchase_url.startswith("http"):
            raise WhopError(f"Whop response missing purchase_url: {str(data)[:300]}")
        plan = data.get("plan") if isinstance(data.get("plan"), dict) else {}
        plan_id = plan.get("id") or data.get("plan_id") or None

        return PaymentInstructions(
            provider=self.provider_key,
            summary="Pay by card or Apple Pay",
            details={
                # The ch_ id is what we can correlate at creation time;
                # the pay_ id only exists once the customer pays and
                # replaces it on the row when the order is marked paid.
                "provider_payment_id": config_id,
                "checkout_configuration_id": config_id,
                "checkout_url": purchase_url,
                "usd_total_cents": order.total_cents,
                "plan_id": plan_id,
            },
        )

    # -- webhook verification ------------------------------------------------

    def verify_webhook(self, headers: dict[str, str], raw_body: bytes) -> VerifiedEvent:
        """Standard Webhooks verification: the three headers, a fresh
        timestamp, and an HMAC over id.timestamp.body that matches one of
        the v1 signatures. Any failure raises — app/api/webhooks.py turns
        that into a 400 and never calls handle_event."""
        secret = _require_webhook_secret()  # blank secret → every webhook rejected
        norm = {k.lower(): v for k, v in headers.items()}
        msg_id = (norm.get("webhook-id") or "").strip()
        timestamp_header = (norm.get("webhook-timestamp") or "").strip()
        signature_header = (norm.get("webhook-signature") or "").strip()
        if not msg_id or not timestamp_header or not signature_header:
            raise WhopError("Missing webhook-id / webhook-timestamp / webhook-signature header.")
        try:
            timestamp = int(timestamp_header)
        except ValueError as exc:
            raise WhopError("webhook-timestamp is not an integer.") from exc
        if abs(time.time() - timestamp) > _WEBHOOK_TOLERANCE_SECONDS:
            raise WhopError("webhook-timestamp is outside the 5-minute tolerance.")
        expected = compute_signature(secret, msg_id, timestamp, raw_body)
        candidates = [part for part in signature_header.split() if part.startswith("v1,")]
        if not any(hmac.compare_digest(expected, candidate) for candidate in candidates):
            raise WhopError("webhook-signature does not match.")

        try:
            body = json.loads(raw_body)
        except ValueError as exc:
            raise WhopError(f"Unparseable JSON webhook body: {exc}") from exc
        if not isinstance(body, dict):
            raise WhopError("Webhook body is not an object.")
        event_type = body.get("type")
        data = body.get("data")
        if not isinstance(event_type, str) or not event_type:
            raise WhopError("Webhook body has no event type.")
        if not isinstance(data, dict):
            raise WhopError("Webhook body has no data object.")
        # external_id = the envelope's msg_ id: Whop retries a delivery
        # with the same id, so the route's UNIQUE(source, external_id)
        # dedupes it, while every distinct event (pending → succeeded)
        # has its own id and still processes.
        return VerifiedEvent(
            external_id=str(body.get("id") or msg_id),
            event_type=event_type,
            order_id=_order_number_from(data),
            raw=body,
        )

    # -- verified event handling ---------------------------------------------

    def handle_event(self, session: Session, event: VerifiedEvent) -> uuid.UUID | None:
        """Map a verified payment event onto the existing order-state
        transitions. Does not commit — app/api/webhooks.py owns the
        transaction boundary. Returns the order id when this event
        marked the order paid, else None."""
        raw_data = event.raw.get("data")
        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
        pay_id = str(data.get("id") or "")
        config_id = str(data.get("checkout_configuration_id") or "")

        payment = self._resolve_payment(session, pay_id, config_id, event.order_id)
        if payment is None:
            # A payment we didn't create (another product on the same
            # Whop account, a dashboard test) or a stale delivery for a
            # row that was cleaned up.
            logger.warning(
                "Whop webhook %s (%s) for unknown payment %r / checkout %r / order %r — ignored.",
                event.external_id,
                event.event_type,
                pay_id,
                config_id,
                event.order_id,
            )
            return None
        order = session.get(Order, payment.order_id)
        if order is None:
            logger.error("Whop payment %s has a Payment row but no order — ignored.", pay_id or config_id)
            return None
        if event.order_id and event.order_id != order.public_order_number:
            logger.error(
                "Whop payment %s carries order_number %r but belongs to order %s — refused.",
                pay_id or config_id,
                event.order_id,
                order.public_order_number,
            )
            return None

        if event.event_type == _PAID_EVENT:
            return self._handle_paid(session, order, payment, pay_id, data, event)

        if payment.status == "succeeded":
            # A late pending/failed delivery for a payment that already
            # paid the order must never downgrade the row.
            self._record(session, payment, event, data)
            logger.info("Whop event %s after payment succeeded — recorded only.", event.event_type)
        elif event.event_type in _PAYMENT_STATUS_FOR:
            payment.status = _PAYMENT_STATUS_FOR[event.event_type]
            session.add(payment)
            self._record(session, payment, event, data)
            logger.info(
                "Whop event %s — payment row %s, order %s stays pending.",
                event.event_type,
                payment.status,
                order.public_order_number,
            )
        else:
            # refund.* / dispute.* / payment.created / anything Whop adds
            # later: record, no transition.
            self._record(session, payment, event, data)
            logger.info("Whop event %s — recorded, no state transition.", event.event_type)
        # Flush like mark_order_paid does, so the row is consistent for
        # anything that reads it in this transaction; the route commits.
        session.flush()
        return None

    @staticmethod
    def _resolve_payment(
        session: Session, pay_id: str, config_id: str, order_number: str | None
    ) -> Payment | None:
        """The Payment row this event is about: by the pay_ id (stamped on
        the row once paid) or the ch_ id (stamped at creation), else by
        the order number the checkout's metadata carried — the newest
        whop row of that order — for a checkout we never managed to
        record an id for."""
        ids = [value for value in (pay_id, config_id) if value]
        if ids:
            payment = (
                session.execute(
                    select(Payment).where(Payment.provider == "whop", Payment.provider_payment_id.in_(ids))
                )
                .scalars()
                .first()
            )
            if payment is not None:
                return payment
        if order_number:
            order = session.execute(
                select(Order).where(Order.public_order_number == order_number)
            ).scalar_one_or_none()
            if order is not None:
                return (
                    session.execute(
                        select(Payment)
                        .where(Payment.order_id == order.id, Payment.provider == "whop")
                        .order_by(Payment.created_at.desc(), Payment.id.desc())
                        .limit(1)
                    )
                    .scalars()
                    .first()
                )
        return None

    def _handle_paid(
        self,
        session: Session,
        order: Order,
        payment: Payment,
        pay_id: str,
        data: dict[str, Any],
        event: VerifiedEvent,
    ) -> uuid.UUID | None:
        if order.status != OrderStatus.PAYMENT_PENDING:
            logger.info(
                "Whop paid webhook for order %s which is already %s — no-op.",
                order.public_order_number,
                order.status,
            )
            return None
        if not pay_id:
            raise WhopError(f"payment.succeeded without a payment id — refusing to mark order {order.public_order_number} paid.")
        # Defense in depth: the signature proves Whop sent this, but ask
        # Whop for the payment itself before moving money-state. Raising
        # (rather than returning) on a disagreement or a network failure
        # makes the route answer 500 with nothing committed, so the same
        # event can be redelivered and processed once Whop really reports
        # it paid.
        fresh = fetch_payment(pay_id)
        if not _reads_paid(fresh):
            raise WhopError(
                f"Whop reports payment {pay_id} as status={fresh.get('status')!r} "
                f"substatus={fresh.get('substatus')!r}, not paid — refusing to mark order "
                f"{order.public_order_number} paid."
            )

        # The amount: from the re-fetched payment first (its shape follows
        # OUR pin), the webhook body as a fallback (its shape follows the
        # webhook's pin). A short or unreadable amount blocks — the money
        # is real, so the order waits for a person rather than shipping
        # against a discount we never offered.
        dollars, currency = _amount_fields(fresh)
        if dollars is None:
            dollars, currency = _amount_fields(data)
        expected_cents = payment.amount_cents
        if currency not in (None, "usd"):
            self._block(session, order, payment, pay_id, event, data, reason="currency", dollars=dollars, currency=currency)
            return None
        if dollars is None:
            self._block(session, order, payment, pay_id, event, data, reason="unreadable", dollars=None, currency=currency)
            return None
        paid_cents = _to_cents(dollars)
        if paid_cents < expected_cents:
            self._block(session, order, payment, pay_id, event, data, reason="underpaid", dollars=dollars, currency=currency)
            return None
        if paid_cents > expected_cents:
            # More than we asked for (Whop-side tax, most likely): the
            # order is paid, but say so in the history.
            logger.warning(
                "Whop payment %s paid %d cents but order %s expects %d — marking paid, recorded.",
                pay_id,
                paid_cents,
                order.public_order_number,
                expected_cents,
            )
            session.add(
                OrderEvent(
                    order_id=order.id,
                    event_type="payment_amount_mismatch",
                    data={
                        "payment_id": pay_id,
                        "reason": "overpaid",
                        "paid_cents": paid_cents,
                        "expected_cents": expected_cents,
                        "currency": currency or "usd",
                    },
                )
            )

        # New dict (not an in-place update) so SQLAlchemy notices the
        # JSONB change; checkout_url stays so the order page can still
        # explain what was paid.
        payment.provider_data = {
            **(payment.provider_data or {}),
            "payment_id": pay_id,
            "card_brand": _scalar(fresh.get("card_brand")),
            "card_last4": _scalar(fresh.get("card_last4")),
            "payment_method_type": _scalar(fresh.get("payment_method_type")),
            "paid_at": _scalar(fresh.get("paid_at")),
            "paid_total": dollars,
        }
        session.add(payment)
        try:
            payment_services.mark_order_paid(
                session,
                order_id=order.id,
                provider=self.provider_key,
                provider_payment_id=pay_id,
                source="whop:webhook",
                payment_id=payment.id,
            )
        except payment_services.PaymentActionError as exc:
            logger.info("Whop paid webhook for %s is a no-op: %s", order.public_order_number, exc)
            return None
        self._record(session, payment, event, data)
        logger.info("Order %s marked paid from Whop payment %s.", order.public_order_number, pay_id)
        return order.id

    def _block(
        self,
        session: Session,
        order: Order,
        payment: Payment,
        pay_id: str,
        event: VerifiedEvent,
        data: dict[str, Any],
        *,
        reason: str,
        dollars: float | None,
        currency: str | None,
    ) -> None:
        """A paid webhook whose amount we will not accept on its own:
        record it on the order for staff (admin Mark paid resolves it),
        flip the row to `underpaid` so the order page stops offering Pay
        Now, and leave the order PAYMENT_PENDING."""
        paid_cents = _to_cents(dollars) if dollars is not None else None
        logger.error(
            "Whop payment %s for order %s blocked (%s): paid=%s %s, expected %d usd cents — order stays pending.",
            pay_id,
            order.public_order_number,
            reason,
            paid_cents,
            currency,
            payment.amount_cents,
        )
        if payment.status != "succeeded":
            payment.status = "underpaid"
            session.add(payment)
        session.add(
            OrderEvent(
                order_id=order.id,
                event_type="payment_amount_mismatch",
                data={
                    "payment_id": pay_id,
                    "reason": reason,
                    "paid_cents": paid_cents,
                    "expected_cents": payment.amount_cents,
                    "currency": currency,
                    "raw_total": _scalar(data.get("total")),
                },
            )
        )
        self._record(session, payment, event, data)
        session.flush()

    @staticmethod
    def _record(session: Session, payment: Payment, event: VerifiedEvent, data: dict[str, Any]) -> None:
        total, currency = _amount_fields(data)
        session.add(
            PaymentEvent(
                payment_id=payment.id,
                provider_event_id=event.external_id,
                event_type=event.event_type,
                data={
                    "payment_id": _scalar(data.get("id")),
                    "checkout_configuration_id": _scalar(data.get("checkout_configuration_id")),
                    "status": _scalar(data.get("status")),
                    "substatus": _scalar(data.get("substatus")),
                    "total": total,
                    "currency": currency,
                    "failure_message": _scalar(data.get("failure_message")),
                    "decline_code": _scalar(data.get("decline_code")),
                },
            )
        )
