"""PayPal Checkout payment provider (PayPal wallet, USD, hosted approval page).

Implements the PaymentProvider protocol from app/payments/base.py so it
drops into app/payments/registry.py and the existing webhook route
without touching the order-status state machine (see
app/services/payments.py — mark_order_paid / mark_order_payment_failed
remain the only transition path, exactly as base.py's docstring
promises). Registered as "paypal" (David, 2026-09-13, TCP site first).
Modelled on app/payments/opennode.py; the one structural difference is
that PayPal's approval page cannot be embedded, so the customer is sent
to it and comes back to our order page, where the payment is captured
(see capture_for_return and app/api/checkout.py).

PayPal REST facts this module relies on (developer.paypal.com, checked
2026-09-13):

- Bases: https://api-m.paypal.com (live) and
  https://api-m.sandbox.paypal.com (sandbox) — Settings.paypal_environment
  picks one.
- Auth: OAuth2 client credentials. POST /v1/oauth2/token with HTTP Basic
  (client id : secret) and body grant_type=client_credentials answers
  {"access_token", "expires_in"} (about 9 hours). Cached per process and
  refreshed a minute early.
- POST /v2/checkout/orders with intent CAPTURE, one purchase unit (USD
  value in dollars with two decimals, custom_id = our order number) and
  payment_source.paypal.experience_context (brand_name, PAY_NOW,
  NO_SHIPPING, return_url, cancel_url) creates a PayPal order:
  {"id", "status": "PAYER_ACTION_REQUIRED", "links": [{"rel":
  "payer-action", "href": ...}]}. The older application_context form
  answers status CREATED with rel "approve"; both rels are accepted. The
  customer must open that href; PayPal sends them back to return_url with
  ?token=<PayPal order id>&PayerID=... appended (cancel_url gets token
  only).
- An order must be approved and captured within 3 hours of creation
  (PayPal's default; an account manager can extend it), so the stored
  expires_at is created + 3 h and the order page mints a new PayPal order
  after that.
- POST /v2/checkout/orders/{id}/capture answers 201 {"status":
  "COMPLETED", "purchase_units": [{"payments": {"captures": [{"id",
  "status", "amount": {"currency_code", "value"}}]}}]}. A 422
  UNPROCESSABLE_ENTITY carries details[0].issue: ORDER_NOT_APPROVED (the
  buyer never approved) or ORDER_ALREADY_CAPTURED (a second capture —
  treated as success after a re-fetch). A capture can also come back
  PENDING (review, eCheck); the order then stays pending until
  PAYMENT.CAPTURE.COMPLETED settles it. payment_method_preference
  IMMEDIATE_PAYMENT_REQUIRED keeps that rare.
- GET /v2/checkout/orders/{id} is the source of truth for the status and
  the captured amount, and is consulted before any order is marked paid.
- Webhooks: JSON body {"id": "WH-…", "event_type", "resource"} plus the
  PAYPAL-AUTH-ALGO / PAYPAL-CERT-URL / PAYPAL-TRANSMISSION-ID /
  PAYPAL-TRANSMISSION-SIG / PAYPAL-TRANSMISSION-TIME headers. Verified
  with POST /v1/notifications/verify-webhook-signature (bearer auth):
  those five values, the webhook id from the dashboard, and the raw body
  spliced in byte-for-byte (PayPal warns that re-serialising the event
  can fail verification) → {"verification_status": "SUCCESS" |
  "FAILURE"}. Any non-2xx answer makes PayPal retry up to 25 times over
  3 days. The event id is the dedupe key (WebhookEvent UNIQUE(source,
  external_id)); PayPal's manual "resend" is keyed by that same id.
- Events: PAYMENT.CAPTURE.COMPLETED (resource = the capture: id,
  status, amount, custom_id, supplementary_data.related_ids.order_id)
  marks the order paid after the re-fetch above. CHECKOUT.ORDER.APPROVED
  (resource = the order) captures server-side, so a customer who closes
  the browser between approving and landing back here still ends up
  paid. PAYMENT.CAPTURE.DENIED marks the payment row failed;
  PAYMENT.CAPTURE.REFUNDED / REVERSED and anything else are recorded on
  the payment (and the order's history) without a state change.

Compliance (David): everything PayPal shows or stores — brand_name,
description, custom_id — carries only the store name and the order
number, never a product name. Same rule as the OpenNode description and
the Venmo/Zelle memos.

Fail-closed behaviour: with PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET
blank, creating a PayPal order raises PayPalNotConfigured at call time
(never at import), which the checkout flow turns into "order created, no
PayPal link yet" (the order page's Continue to PayPal button mints one
later) rather than a broken checkout. With the credentials or
PAYPAL_WEBHOOK_ID blank, every webhook is rejected 400.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
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

_HTTP_TIMEOUT_SECONDS = 20.0
# How long a PayPal order stays approvable/capturable (PayPal default).
_ORDER_TTL_SECONDS = 3 * 60 * 60
# PayPal captures are exact dollars-and-cents, so anything beyond
# floating-point rounding is a real disagreement.
_AMOUNT_TOLERANCE = 0.005
_API_BASES = {
    "live": "https://api-m.paypal.com",
    "sandbox": "https://api-m.sandbox.paypal.com",
}
# The HATEOAS rel that carries the customer-facing approval URL.
_APPROVE_RELS = ("payer-action", "approve")
# verify-webhook-signature field → the inbound header it comes from.
_SIGNATURE_HEADERS = {
    "auth_algo": "paypal-auth-algo",
    "cert_url": "paypal-cert-url",
    "transmission_id": "paypal-transmission-id",
    "transmission_sig": "paypal-transmission-sig",
    "transmission_time": "paypal-transmission-time",
}

EVENT_CAPTURE_COMPLETED = "PAYMENT.CAPTURE.COMPLETED"
EVENT_CAPTURE_DENIED = "PAYMENT.CAPTURE.DENIED"
EVENT_CAPTURE_REFUNDED = "PAYMENT.CAPTURE.REFUNDED"
EVENT_CAPTURE_REVERSED = "PAYMENT.CAPTURE.REVERSED"
EVENT_ORDER_APPROVED = "CHECKOUT.ORDER.APPROVED"
# What the webhook registered in the PayPal dashboard should subscribe
# to. Unknown events are recorded and ignored, so "all events" works too.
WEBHOOK_EVENT_TYPES = (
    EVENT_CAPTURE_COMPLETED,
    EVENT_CAPTURE_DENIED,
    EVENT_CAPTURE_REFUNDED,
    EVENT_CAPTURE_REVERSED,
    EVENT_ORDER_APPROVED,
)
# OrderEvent types written for admin history on the non-paid events.
_ORDER_EVENT_FOR = {
    EVENT_CAPTURE_DENIED: "payment_denied",
    EVENT_CAPTURE_REFUNDED: "payment_refunded",
    EVENT_CAPTURE_REVERSED: "payment_reversed",
}


class PayPalError(RuntimeError):
    """Any PayPal-side failure (HTTP error, unexpected payload, bad
    signature). Checkout catches this and degrades gracefully — the
    order still exists, the approval link just isn't attached."""


class PayPalNotConfigured(PayPalError):
    """Credentials (or, for webhooks, the webhook id) are blank. Raised
    lazily at call time, never at import or registration time, so the
    app boots fine without keys."""


class PayPalOrderNotApproved(PayPalError):
    """Capture refused because the buyer has not approved the PayPal
    order — they left PayPal early, or came back before approving."""


class _PayPalAlreadyCaptured(PayPalError):
    """Internal: a second capture of an order PayPal already captured.
    Callers re-fetch the order and settle from that instead."""


# --- HTTP plumbing -----------------------------------------------------------


def _client() -> httpx.Client:
    """Fresh client per call, like the OpenNode provider — a handful of
    calls per order, so simplicity beats a shared pool. Tests
    monkeypatch this."""
    return httpx.Client(timeout=_HTTP_TIMEOUT_SECONDS)


def _require_credentials() -> tuple[str, str]:
    settings = get_settings()
    client_id = settings.paypal_client_id.strip()
    secret = settings.paypal_client_secret.strip()
    if not client_id or not secret:
        raise PayPalNotConfigured("PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are not configured.")
    return client_id, secret


def _environment() -> str:
    env = get_settings().paypal_environment.strip().lower()
    if env not in _API_BASES:
        raise PayPalError(f"PAYPAL_ENVIRONMENT must be one of {sorted(_API_BASES)}, not {env!r}.")
    return env


def _api_base() -> str:
    return _API_BASES[_environment()]


_token_lock = threading.Lock()
_token_cache: dict[str, Any] = {"value": None, "expires_at": 0.0, "key": None}


def _reset_token_cache() -> None:
    """For tests and key rotation."""
    with _token_lock:
        _token_cache.update(value=None, expires_at=0.0, key=None)


def _access_token() -> str:
    """A bearer token for the configured app, cached per process until a
    minute before PayPal says it expires. Raises PayPalNotConfigured on
    blank credentials and PayPalError when PayPal refuses them."""
    client_id, secret = _require_credentials()
    cache_key = (client_id, _environment())
    now = time.monotonic()
    with _token_lock:
        if _token_cache["key"] == cache_key and _token_cache["value"] and now < _token_cache["expires_at"] - 60:
            return _token_cache["value"]
    try:
        with _client() as client:
            response = client.post(
                f"{_api_base()}/v1/oauth2/token",
                auth=(client_id, secret),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise PayPalError(f"PayPal token request failed: {exc}") from exc
    if response.status_code != 200:
        raise PayPalError(f"PayPal token request failed ({response.status_code}): {response.text[:300]}")
    data = _json(response, "token")
    token = str(data.get("access_token") or "")
    if not token:
        raise PayPalError("PayPal token response carries no access_token.")
    try:
        expires_in = int(data.get("expires_in") or 0)
    except (TypeError, ValueError):
        expires_in = 0
    with _token_lock:
        _token_cache.update(value=token, expires_at=now + max(expires_in, 120), key=cache_key)
    return token


def _auth_headers(token: str, *, request_id: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Full resource in create/capture responses, not just id + links.
        "Prefer": "return=representation",
    }
    if request_id:
        # PayPal's idempotency key: a retried capture with the same id
        # gets the same answer instead of ORDER_ALREADY_CAPTURED.
        headers["PayPal-Request-Id"] = request_id
    return headers


def _json(response: Any, what: str) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise PayPalError(f"PayPal {what} response is not JSON.") from exc
    if not isinstance(data, dict):
        raise PayPalError(f"PayPal {what} response is not an object.")
    return data


def _issue(response: Any) -> str:
    """details[0].issue of a PayPal error body ("ORDER_NOT_APPROVED",
    "ORDER_ALREADY_CAPTURED", …), or "" when there is none."""
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    details = body.get("details")
    if isinstance(details, list) and details and isinstance(details[0], dict):
        return str(details[0].get("issue") or "").upper()
    return str(body.get("name") or "").upper()


def _dollars(cents: int) -> str:
    return f"{cents / 100:.2f}"


def _approve_url(data: dict[str, Any]) -> str | None:
    links = data.get("links")
    if not isinstance(links, list):
        return None
    for rel in _APPROVE_RELS:
        for link in links:
            if isinstance(link, dict) and str(link.get("rel") or "").lower() == rel and link.get("href"):
                return str(link["href"])
    return None


def _captures(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Every capture on an order object (create/capture/get responses)."""
    found: list[dict[str, Any]] = []
    units = data.get("purchase_units")
    if not isinstance(units, list):
        return found
    for unit in units:
        payments = unit.get("payments") if isinstance(unit, dict) else None
        captures = payments.get("captures") if isinstance(payments, dict) else None
        if isinstance(captures, list):
            found.extend(c for c in captures if isinstance(c, dict))
    return found


def _capture_summary(capture: dict[str, Any]) -> dict[str, Any]:
    amount = capture.get("amount") if isinstance(capture.get("amount"), dict) else {}
    return {
        "capture_id": str(capture.get("id") or ""),
        "status": str(capture.get("status") or "").upper(),
        "value": str(amount.get("value") or ""),
        "currency": str(amount.get("currency_code") or "").upper(),
    }


def _settled_capture(data: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """("completed", capture) when the order carries a COMPLETED capture,
    ("pending", capture) when only a PENDING one, else ("none", None)."""
    captures = [_capture_summary(c) for c in _captures(data)]
    for capture in captures:
        if capture["status"] == "COMPLETED":
            return "completed", capture
    for capture in captures:
        if capture["status"] == "PENDING":
            return "pending", capture
    return "none", None


# --- PayPal API calls ----------------------------------------------------------


def fetch_order(paypal_order_id: str) -> dict[str, Any]:
    """GET the order from PayPal — the source of truth for its status and
    captured amount. Raises PayPalError on any failure so the caller can
    refuse to act."""
    token = _access_token()
    try:
        with _client() as client:
            response = client.get(f"{_api_base()}/v2/checkout/orders/{paypal_order_id}", headers=_auth_headers(token))
    except httpx.HTTPError as exc:
        raise PayPalError(f"PayPal order lookup for {paypal_order_id} failed: {exc}") from exc
    if response.status_code != 200:
        raise PayPalError(
            f"PayPal order lookup for {paypal_order_id} failed ({response.status_code}): {response.text[:300]}"
        )
    return _json(response, "order lookup")


def capture_paypal_order(paypal_order_id: str) -> dict[str, Any]:
    """POST the capture. Returns the order object on success (status
    COMPLETED, or PENDING when PayPal is still completing it). Raises
    PayPalOrderNotApproved when the buyer never approved,
    _PayPalAlreadyCaptured when a previous capture already went through,
    PayPalError otherwise."""
    token = _access_token()
    try:
        with _client() as client:
            response = client.post(
                f"{_api_base()}/v2/checkout/orders/{paypal_order_id}/capture",
                headers=_auth_headers(token, request_id=f"{paypal_order_id}:capture"),
                content=b"{}",
            )
    except httpx.HTTPError as exc:
        raise PayPalError(f"PayPal capture of {paypal_order_id} failed: {exc}") from exc
    if response.status_code in (200, 201):
        return _json(response, "capture")
    issue = _issue(response)
    if issue == "ORDER_ALREADY_CAPTURED":
        raise _PayPalAlreadyCaptured(f"PayPal order {paypal_order_id} was already captured.")
    if issue == "ORDER_NOT_APPROVED":
        raise PayPalOrderNotApproved(f"PayPal order {paypal_order_id} has not been approved by the buyer.")
    raise PayPalError(
        f"PayPal capture of {paypal_order_id} failed ({response.status_code}{', ' + issue if issue else ''}): "
        f"{response.text[:300]}"
    )


def register_webhook(url: str, event_types: tuple[str, ...] = WEBHOOK_EVENT_TYPES) -> dict[str, Any]:
    """POST /v1/notifications/webhooks — one-off setup helper (David or
    an operator runs it once per environment; see
    docs/plans/paypal-checkout.md). Returns PayPal's webhook object; its
    `id` is what PAYPAL_WEBHOOK_ID must be set to."""
    token = _access_token()
    try:
        with _client() as client:
            response = client.post(
                f"{_api_base()}/v1/notifications/webhooks",
                headers=_auth_headers(token),
                json={"url": url, "event_types": [{"name": name} for name in event_types]},
            )
    except httpx.HTTPError as exc:
        raise PayPalError(f"PayPal webhook registration failed: {exc}") from exc
    if response.status_code not in (200, 201):
        raise PayPalError(f"PayPal webhook registration failed ({response.status_code}): {response.text[:300]}")
    return _json(response, "webhook registration")


def list_webhooks() -> list[dict[str, Any]]:
    token = _access_token()
    try:
        with _client() as client:
            response = client.get(f"{_api_base()}/v1/notifications/webhooks", headers=_auth_headers(token))
    except httpx.HTTPError as exc:
        raise PayPalError(f"PayPal webhook listing failed: {exc}") from exc
    if response.status_code != 200:
        raise PayPalError(f"PayPal webhook listing failed ({response.status_code}): {response.text[:300]}")
    hooks = _json(response, "webhook listing").get("webhooks")
    return [h for h in hooks if isinstance(h, dict)] if isinstance(hooks, list) else []


def build_verify_body(signature: dict[str, str], webhook_id: str, raw_body: bytes) -> bytes:
    """The verify-webhook-signature request: the five header values and
    the webhook id serialised normally, with the event spliced in as the
    exact bytes PayPal delivered. Module-level so tests can assert the
    splice."""
    head = json.dumps({**signature, "webhook_id": webhook_id}, separators=(",", ":"))
    return head[:-1].encode("utf-8") + b',"webhook_event":' + raw_body.strip() + b"}"


# --- provider --------------------------------------------------------------------


class PayPalProvider:
    provider_key = "paypal"

    # -- order creation ---------------------------------------------------

    def create_payment_instructions(self, order: Order) -> PaymentInstructions:
        """Create a PayPal order for the order's USD total and return the
        approval URL the customer must be sent to."""
        token = _access_token()  # raises PayPalNotConfigured on blank credentials
        settings = get_settings()
        site = settings.public_site_url.strip().rstrip("/")
        if not (site.startswith("https://") or site.startswith("http://")):
            # Without a return URL the customer would be stranded on
            # PayPal after approving; refusing here keeps "PayPal is on"
            # and "PayPal works" the same thing.
            raise PayPalNotConfigured("PUBLIC_SITE_URL must be set so PayPal can send the customer back to the order page.")
        order_url = f"{site}/order/{order.access_token}"
        brand = settings.paypal_brand_name.strip() or "TCP"

        payload: dict[str, Any] = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": "default",
                    # Our order number, echoed on the capture and its
                    # webhook (resource.custom_id) for the cross-check.
                    "custom_id": order.public_order_number,
                    # Shown on PayPal's approval page and in the payer's
                    # record — order number only, per the memo rule.
                    "description": f"{brand} Order {order.public_order_number}",
                    "amount": {"currency_code": "USD", "value": _dollars(order.total_cents)},
                }
            ],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "brand_name": brand,
                        "user_action": "PAY_NOW",
                        # We already collected the shipping address; PayPal
                        # neither shows nor validates one.
                        "shipping_preference": "NO_SHIPPING",
                        # Refuse funding that would leave the capture
                        # PENDING (eCheck), so approval means paid.
                        "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
                        "return_url": order_url,
                        "cancel_url": order_url,
                    }
                }
            },
        }

        try:
            with _client() as client:
                response = client.post(f"{_api_base()}/v2/checkout/orders", headers=_auth_headers(token), json=payload)
        except httpx.HTTPError as exc:
            raise PayPalError(f"PayPal order creation failed: {exc}") from exc
        if response.status_code not in (200, 201):
            raise PayPalError(f"PayPal order creation failed ({response.status_code}): {response.text[:300]}")
        data = _json(response, "order creation")
        paypal_order_id = str(data.get("id") or "")
        if not paypal_order_id:
            raise PayPalError(f"PayPal response missing the order id: {str(data)[:300]}")
        approve_url = _approve_url(data)
        if not approve_url:
            raise PayPalError(f"PayPal order {paypal_order_id} carries no approval link: {str(data)[:300]}")

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=_ORDER_TTL_SECONDS)
        return PaymentInstructions(
            provider=self.provider_key,
            summary="Pay with PayPal",
            details={
                "provider_payment_id": paypal_order_id,
                "approve_url": approve_url,
                # The generic name the order page already knows for
                # "where the customer pays".
                "checkout_url": approve_url,
                "usd_total_cents": order.total_cents,
                "expires_in_seconds": _ORDER_TTL_SECONDS,
                "expires_at": expires_at.isoformat(),
                "paypal_status": str(data.get("status") or ""),
            },
        )

    # -- webhook verification ---------------------------------------------

    def verify_webhook(self, headers: dict[str, str], raw_body: bytes) -> VerifiedEvent:
        """Ask PayPal whether the transmission headers really sign this
        body for our webhook id. Any failure raises — app/api/webhooks.py
        turns that into a 400 and never calls handle_event."""
        webhook_id = get_settings().paypal_webhook_id.strip()
        if not webhook_id:
            raise PayPalNotConfigured("PAYPAL_WEBHOOK_ID is not configured.")
        token = _access_token()  # blank credentials → every webhook rejected
        norm = {k.lower(): v for k, v in headers.items()}
        signature: dict[str, str] = {}
        for field, header in _SIGNATURE_HEADERS.items():
            value = (norm.get(header) or "").strip()
            if not value:
                raise PayPalError(f"Missing {header} header.")
            signature[field] = value
        if not raw_body or not raw_body.strip():
            raise PayPalError("Empty webhook body.")
        try:
            event = json.loads(raw_body)
        except ValueError as exc:
            raise PayPalError(f"Unparseable JSON webhook body: {exc}") from exc
        if not isinstance(event, dict) or not isinstance(event.get("resource"), dict):
            raise PayPalError("Webhook body is not an event object.")
        event_id = str(event.get("id") or "").strip()
        event_type = str(event.get("event_type") or "").strip().upper()
        if not event_id or not event_type:
            raise PayPalError("Webhook body has no id / event_type.")

        try:
            with _client() as client:
                response = client.post(
                    f"{_api_base()}/v1/notifications/verify-webhook-signature",
                    headers=_auth_headers(token),
                    content=build_verify_body(signature, webhook_id, raw_body),
                )
        except httpx.HTTPError as exc:
            raise PayPalError(f"PayPal signature verification failed: {exc}") from exc
        if response.status_code != 200:
            raise PayPalError(f"PayPal signature verification failed ({response.status_code}): {response.text[:300]}")
        status = str(_json(response, "signature verification").get("verification_status") or "").upper()
        if status != "SUCCESS":
            raise PayPalError(f"PayPal reports the webhook signature as {status or 'unknown'}.")

        return VerifiedEvent(
            # PayPal's event id is stable across its retries and manual
            # resends, so a redelivery dedupes at the route.
            external_id=event_id,
            event_type=event_type,
            order_id=_custom_id(event["resource"]),
            raw=event,
        )

    # -- verified event handling ---------------------------------------------

    def handle_event(self, session: Session, event: VerifiedEvent) -> uuid.UUID | None:
        """Map a verified event onto the existing order-state transitions.
        Does not commit — app/api/webhooks.py owns the transaction
        boundary. Returns the order id when this event marked the order
        paid, else None."""
        resource = event.raw.get("resource") if isinstance(event.raw.get("resource"), dict) else {}
        paypal_order_id = _paypal_order_id(event.event_type, resource)
        if not paypal_order_id:
            logger.warning("PayPal webhook %s (%s) names no order id — ignored.", event.external_id, event.event_type)
            return None

        payment = session.execute(
            select(Payment).where(Payment.provider_payment_id == paypal_order_id)
        ).scalar_one_or_none()
        if payment is None:
            # A PayPal order we didn't create (another app on the same
            # account, the simulator) or a stale delivery.
            logger.warning(
                "PayPal webhook %s for unknown order %s (%s) — ignored.", event.external_id, paypal_order_id, event.event_type
            )
            return None
        order = session.get(Order, payment.order_id)
        if order is None:
            logger.error("PayPal order %s has a Payment row but no order — ignored.", paypal_order_id)
            return None
        if event.order_id and event.order_id != order.public_order_number:
            logger.error(
                "PayPal order %s carries custom_id %r but belongs to order %s — refused.",
                paypal_order_id,
                event.order_id,
                order.public_order_number,
            )
            return None

        if event.event_type == EVENT_CAPTURE_COMPLETED:
            return self._handle_capture_completed(session, order, payment, paypal_order_id, event, resource)
        if event.event_type == EVENT_ORDER_APPROVED:
            return self._handle_order_approved(session, order, payment, paypal_order_id, event, resource)

        if event.event_type == EVENT_CAPTURE_DENIED and payment.status != "succeeded":
            payment.status = "failed"
            session.add(payment)
        order_event = _ORDER_EVENT_FOR.get(event.event_type)
        if order_event:
            capture = _capture_summary(resource)
            session.add(
                OrderEvent(
                    order_id=order.id,
                    event_type=order_event,
                    data={"provider": self.provider_key, "paypal_order_id": paypal_order_id, **capture},
                )
            )
        self._record(session, payment, event, resource)
        logger.info(
            "PayPal order %s event %s — recorded, order %s stays %s.",
            paypal_order_id,
            event.event_type,
            order.public_order_number,
            order.status,
        )
        session.flush()
        return None

    def _handle_capture_completed(
        self,
        session: Session,
        order: Order,
        payment: Payment,
        paypal_order_id: str,
        event: VerifiedEvent,
        resource: dict[str, Any],
    ) -> uuid.UUID | None:
        self._record(session, payment, event, resource)
        if order.status != OrderStatus.PAYMENT_PENDING:
            logger.info(
                "PayPal capture webhook for order %s which is already %s — recorded only.",
                order.public_order_number,
                order.status,
            )
            session.flush()
            return None
        self._lock(session, order)
        if order.status != OrderStatus.PAYMENT_PENDING:
            # The customer's return captured it while we waited for the lock.
            session.flush()
            return None
        # Defense in depth: the signature proves PayPal sent this, but
        # the order is only ever marked paid from what PayPal says right
        # now. Raising (rather than returning) on a lookup failure or a
        # not-COMPLETED answer makes the route answer 500 with nothing
        # committed, so PayPal redelivers and the event is processed once
        # PayPal really reports the capture complete.
        confirmed = fetch_order(paypal_order_id)
        status = str(confirmed.get("status") or "").upper()
        if status != "COMPLETED":
            raise PayPalError(
                f"PayPal reports order {paypal_order_id} as {status!r}, not COMPLETED — "
                f"refusing to mark order {order.public_order_number} paid."
            )
        state, capture = _settled_capture(confirmed)
        if state != "completed" or capture is None:
            raise PayPalError(
                f"PayPal order {paypal_order_id} is COMPLETED but carries no completed capture — "
                f"refusing to mark order {order.public_order_number} paid."
            )
        if not self._amount_matches(session, order, paypal_order_id, capture):
            # Recorded on the order for admin, answered 200 so PayPal
            # stops retrying; a person sorts out the difference.
            session.flush()
            return None
        return self._settle(session, order, payment, paypal_order_id, capture, source="paypal:webhook")

    def _handle_order_approved(
        self,
        session: Session,
        order: Order,
        payment: Payment,
        paypal_order_id: str,
        event: VerifiedEvent,
        resource: dict[str, Any],
    ) -> uuid.UUID | None:
        """The buyer approved on PayPal. Normally their browser lands on
        our order page a moment later and captures; capturing here too
        covers the customer who closed the tab in between. Best effort:
        a capture failure is logged, the event is still acknowledged, and
        the customer's return or a later PAYMENT.CAPTURE.COMPLETED settles
        the order."""
        self._record(session, payment, event, resource)
        if order.status != OrderStatus.PAYMENT_PENDING or payment.status == "succeeded":
            session.flush()
            return None
        self._lock(session, order)
        if order.status != OrderStatus.PAYMENT_PENDING:
            session.flush()
            return None
        try:
            return self._capture_and_settle(session, order, payment, paypal_order_id, source="paypal:webhook_approved")
        except PayPalOrderNotApproved:
            logger.info("PayPal says order %s is not approved after all — order %s stays pending.", paypal_order_id, order.public_order_number)
        except PayPalError as exc:
            logger.warning("PayPal capture on approval of %s failed: %s", paypal_order_id, exc)
        session.flush()
        return None

    # -- the customer's return from PayPal -------------------------------------

    def capture_for_return(self, session: Session, order: Order) -> uuid.UUID | None:
        """Called by POST /shop/orders/{token}/paypal/capture when the
        customer lands back on the order page. Captures the order's
        current PayPal order and marks the order paid when PayPal reports
        the capture complete. Does not commit. Returns the order id when
        this call marked it paid, None when it was already paid (the
        webhook won) or the capture is still pending. Raises
        PayPalOrderNotApproved when the buyer never approved, PayPalError
        for anything else."""
        if order.status != OrderStatus.PAYMENT_PENDING:
            return None
        payment = payment_services.display_payment(order)
        if payment is None or payment.provider != self.provider_key or not payment.provider_payment_id:
            raise PayPalError("This order has no PayPal payment to capture.")
        if payment.status not in ("pending", "processing"):
            raise PayPalError(f"The PayPal payment for this order is {payment.status}, not payable.")
        self._lock(session, order)
        if order.status != OrderStatus.PAYMENT_PENDING:
            # The webhook captured it while we waited for the lock.
            return None
        return self._capture_and_settle(session, order, payment, payment.provider_payment_id, source="paypal:capture")

    # -- shared settlement -------------------------------------------------------

    def _capture_and_settle(
        self, session: Session, order: Order, payment: Payment, paypal_order_id: str, *, source: str
    ) -> uuid.UUID | None:
        try:
            data = capture_paypal_order(paypal_order_id)
        except _PayPalAlreadyCaptured:
            data = fetch_order(paypal_order_id)
        status = str(data.get("status") or "").upper()
        state, capture = _settled_capture(data)
        if status != "COMPLETED" or state != "completed" or capture is None:
            # PayPal is still completing the capture (review, eCheck) or
            # something unexpected: the order stays pending, the row says
            # processing so nothing re-mints over money in flight, and
            # PAYMENT.CAPTURE.COMPLETED settles it later.
            if payment.status != "succeeded":
                payment.status = "processing"
                session.add(payment)
            session.add(
                PaymentEvent(
                    payment_id=payment.id,
                    event_type="paypal.capture_pending",
                    data={"source": source, "paypal_status": status, **(capture or {})},
                )
            )
            session.flush()
            logger.info(
                "PayPal order %s captured but %s/%s — order %s stays pending.", paypal_order_id, status, state, order.public_order_number
            )
            return None
        if not self._amount_matches(session, order, paypal_order_id, capture):
            session.flush()
            return None
        return self._settle(session, order, payment, paypal_order_id, capture, source=source)

    def _settle(
        self,
        session: Session,
        order: Order,
        payment: Payment,
        paypal_order_id: str,
        capture: dict[str, Any],
        *,
        source: str,
    ) -> uuid.UUID | None:
        try:
            payment_services.mark_order_paid(
                session,
                order_id=order.id,
                provider=self.provider_key,
                provider_payment_id=paypal_order_id,
                source=source,
                payment_id=payment.id,
            )
        except payment_services.PaymentActionError as exc:
            logger.info("PayPal settlement of %s is a no-op: %s", order.public_order_number, exc)
            return None
        # Keep the capture on the row for admin/refunds; a new dict so
        # SQLAlchemy notices the JSONB change.
        payment.provider_data = {**(payment.provider_data or {}), "capture_id": capture["capture_id"], "captured_amount": capture["value"], "captured_currency": capture["currency"]}
        session.add(payment)
        session.add(
            PaymentEvent(
                payment_id=payment.id,
                event_type="paypal.capture_completed",
                data={"source": source, **capture},
            )
        )
        session.flush()
        logger.info("Order %s marked paid from PayPal order %s (%s).", order.public_order_number, paypal_order_id, source)
        return order.id

    @staticmethod
    def _amount_matches(session: Session, order: Order, paypal_order_id: str, capture: dict[str, Any]) -> bool:
        """PayPal captures are exact USD, so the captured amount must equal
        the order total to the cent. Unlike the OpenNode check this
        blocks: a mismatch is recorded on the order (payment_amount_mismatch)
        and the order is NOT marked paid."""
        expected = round(order.total_cents / 100, 2)
        try:
            captured = float(capture["value"])
        except (TypeError, ValueError, KeyError):
            captured = None
        if captured is not None and capture.get("currency") == "USD" and abs(captured - expected) <= _AMOUNT_TOLERANCE:
            return True
        logger.error(
            "PayPal order %s captured %s %s but order %s expects %.2f USD — NOT marking paid.",
            paypal_order_id,
            capture.get("value"),
            capture.get("currency"),
            order.public_order_number,
            expected,
        )
        session.add(
            OrderEvent(
                order_id=order.id,
                event_type="payment_amount_mismatch",
                data={
                    "provider": "paypal",
                    "paypal_order_id": paypal_order_id,
                    "capture_id": capture.get("capture_id"),
                    "captured_amount": capture.get("value"),
                    "captured_currency": capture.get("currency"),
                    "expected_usd": expected,
                },
            )
        )
        return False

    @staticmethod
    def _lock(session: Session, order: Order) -> None:
        """Serialise the two paths that can mark a PayPal order paid — the
        customer's return (capture endpoint) and the webhook — on the
        order row, so whichever comes second sees the first one's result
        instead of racing it."""
        session.execute(select(Order.id).where(Order.id == order.id).with_for_update())
        session.refresh(order)

    @staticmethod
    def _record(session: Session, payment: Payment, event: VerifiedEvent, resource: dict[str, Any]) -> None:
        session.add(
            PaymentEvent(
                payment_id=payment.id,
                provider_event_id=event.external_id,
                event_type=event.event_type.lower(),
                data={"resource_id": resource.get("id"), "resource_status": resource.get("status"), **_capture_summary(resource)},
            )
        )


def _custom_id(resource: dict[str, Any]) -> str | None:
    """Our order number as PayPal echoes it: resource.custom_id on a
    capture, purchase_units[0].custom_id on an order."""
    value = resource.get("custom_id")
    if not value:
        units = resource.get("purchase_units")
        if isinstance(units, list) and units and isinstance(units[0], dict):
            value = units[0].get("custom_id")
    value = str(value or "").strip()
    return value or None


def _paypal_order_id(event_type: str, resource: dict[str, Any]) -> str:
    """The PayPal order id an event is about: the resource itself for
    CHECKOUT.ORDER.* events, supplementary_data.related_ids.order_id for
    capture events."""
    if event_type.startswith("CHECKOUT.ORDER."):
        return str(resource.get("id") or "").strip()
    supplementary = resource.get("supplementary_data")
    related = supplementary.get("related_ids") if isinstance(supplementary, dict) else None
    order_id = related.get("order_id") if isinstance(related, dict) else None
    return str(order_id or "").strip()
