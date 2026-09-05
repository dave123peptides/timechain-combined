"""Speed Bitcoin payment provider (Lightning + on-chain, USD-priced).

Implements the PaymentProvider protocol from app/payments/base.py so it
drops into app/payments/registry.py and the existing webhook route
without touching the order-status state machine (see
app/services/payments.py — mark_order_paid / mark_order_payment_failed
remain the only transition path, exactly as base.py's docstring
promises). Replaced OpenNode (the previous provider, rejected over
support/KYB issues) on 2026-08-28.

Speed API facts this module relies on (apidocs.tryspeed.com,
cross-checked against the source of Speed's official WooCommerce
plugin, which is the reference implementation):

- Base URL: https://api.tryspeed.com (Settings.speed_api_base).
- Auth: HTTP Basic with the API key as the username and NO password —
  literally `Authorization: Basic base64(<key>)`, no trailing colon.
  Keys are `sk_test_` / `sk_live_` (Dashboard → Developers → API Keys).
- Every call carries a `speed-version` header. 2022-10-15 enables
  on-chain + Lightning + ETH/SOL/TRON; 2022-04-15 would be
  Lightning-only. We use 2022-10-15 so customers get the full choice.
- POST /checkout-sessions creates a session. `currency` is the fiat
  base currency ("USD"); `amount` is in MAJOR units (dollars, e.g.
  129.50 — never cents). Response (HTTP 200/201) carries `id`
  ("cs_...") and `default_url` = the hosted payment page the customer
  is sent to.
- Correlation: we store the session `id` as Payment.provider_payment_id
  at creation time. Webhook events for the session carry the same
  `data.object.id`, so handle_event resolves the Payment row by it.
  (This is why the session's `metadata` field is not used — the DB row
  is the source of truth and metadata's wire format is ambiguous.)
- Webhooks are signed. Headers: `webhook-signature` (space-separated
  "v1,<base64>" pairs), `webhook-timestamp`, `webhook-id`. The endpoint
  secret starts with `wsec_`; strip the prefix, Base64-DECODE it to get
  the key bytes, then HMAC-SHA256 over
  `webhook-id + "." + webhook-timestamp + "." + rawBody`, Base64-encode
  the digest, and constant-time compare against each candidate
  signature. (Verified against the plugin's Webhook.php verifier.)
- Events we act on: `checkout_session.paid` (session paid in full,
  tolerance included → mark order paid). `checkout_session.payment_paid`
  is a PARTIAL payment — log only, wait for `.paid`.
  `checkout_session.created` / `checkout_session.deactivated` — log only.

Fail-closed behaviour: with SPEED_API_KEY blank, session creation raises
SpeedNotConfigured, which the checkout route turns into "order created,
no Bitcoin instructions yet" (the order page falls back to the manual
payment note) rather than a broken checkout. With SPEED_WEBHOOK_SECRET
blank, every webhook is rejected 400 — nothing can flip an order to
paid until the endpoint secret exists (it's created when the webhook
endpoint is registered, which needs the public Vercel URL).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.orders import Order
from app.models.payments import Payment
from app.payments.base import PaymentInstructions, VerifiedEvent
from app.services import payments as payment_services

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_SECONDS = 20.0
_SECRET_PREFIX = "wsec_"
# How long a session stays payable. Docs: min 5 minutes, fiat default
# 600 s — far too short for a customer fetching a wallet. One hour.
_SESSION_TTL_SECONDS = 3600
# Amounts compare in dollars; half-a-cent tolerance absorbs float repr.
_AMOUNT_TOLERANCE = 0.01


class SpeedError(RuntimeError):
    """Any Speed-side failure (HTTP error, unexpected payload). Checkout
    catches this and degrades gracefully — the order still exists,
    payment instructions just aren't attached."""


class SpeedNotConfigured(SpeedError):
    """SPEED_API_KEY (or the webhook secret, for inbound events) is
    blank. Raised lazily at call time, never at import/registration
    time, so the app boots fine without keys."""


def _client() -> httpx.Client:
    """Fresh client per call — session creation happens at most once per
    order and webhook verification at most once per delivery, so the
    simplicity beats a shared connection pool. Tests monkeypatch this."""
    return httpx.Client(timeout=_HTTP_TIMEOUT_SECONDS)


def _require_api_key() -> str:
    key = get_settings().speed_api_key
    if not key:
        raise SpeedNotConfigured("SPEED_API_KEY is not configured.")
    return key


def _require_webhook_secret() -> str:
    secret = get_settings().speed_webhook_secret
    if not secret:
        raise SpeedNotConfigured("SPEED_WEBHOOK_SECRET is not configured.")
    return secret


def _auth_headers(api_key: str) -> dict[str, str]:
    # HTTP Basic with the key as username and an EMPTY password —
    # base64(key) with no colon, exactly as Speed's official plugin
    # sends it (Api_Call.php).
    token = base64.b64encode(api_key.encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "speed-version": get_settings().speed_api_version,
    }


def compute_expected_signature(secret: str, msg_id: str, timestamp: str, raw_body: bytes) -> str:
    """The Base64 HMAC-SHA256 a valid `v1,` signature must carry.
    Exposed at module level purely so tests can sign fixtures with the
    same code path production verifies with.

    Raises SpeedError if the secret is malformed (missing `wsec_` prefix
    or not valid Base64) — a misconfigured secret must fail every
    webhook loudly, never verify one by accident."""
    if not secret.startswith(_SECRET_PREFIX):
        raise SpeedError(f"SPEED_WEBHOOK_SECRET must start with {_SECRET_PREFIX!r}.")
    try:
        key_bytes = base64.b64decode(secret[len(_SECRET_PREFIX):], validate=True)
    except (ValueError, TypeError) as exc:
        raise SpeedError("SPEED_WEBHOOK_SECRET is not valid Base64 after the wsec_ prefix.") from exc
    if not key_bytes:
        raise SpeedError("SPEED_WEBHOOK_SECRET decodes to an empty key.")
    signed_payload = f"{msg_id}.{timestamp}.".encode("utf-8") + raw_body
    digest = hmac.new(key_bytes, signed_payload, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


class SpeedProvider:
    provider_key = "crypto"

    # -- session creation ------------------------------------------------

    def create_payment_instructions(self, order: Order) -> PaymentInstructions:
        """Create a Speed checkout session for the order's USD total and
        return what the checkout flow needs to send the customer to the
        hosted payment page (Lightning / on-chain / QR — their choice)."""
        api_key = _require_api_key()  # raises SpeedNotConfigured if no key
        settings = get_settings()

        payload: dict[str, Any] = {
            "currency": "USD",
            # Major units (dollars), not cents — Speed truncates nothing
            # here because the API takes a float; keep exactly two
            # decimals so the hosted page and our ledger agree.
            "amount": round(order.total_cents / 100, 2),
            "description": f"Timechain Peptides Order {order.public_order_number}",
            "ttl": _SESSION_TTL_SECONDS,
            # Branding for the hosted payment page — Speed has no
            # embeddable widget (Speed.js just redirects here too), so
            # the next best thing is making their page read as ours.
            # statement_descriptor shows in the payer's wallet.
            "statement_descriptor": "Timechain Peptides",
            "title": "Timechain Peptides",
            "title_description": f"Order {order.public_order_number} — pay with Bitcoin (Lightning or on-chain). You'll be returned to the site once payment is complete.",
        }
        # Optional logo on the hosted page. PUBLIC_SITE_LOGO_URL must be
        # a stable https URL (e.g. the Vercel-hosted asset); blank = no
        # image, which Speed renders cleanly.
        logo_url = getattr(settings, "public_site_logo_url", "")
        if logo_url.startswith("https://"):
            payload["title_image"] = logo_url
        # Redirects are only valid once the storefront has a public URL
        # (the Vercel deployment). Speed rejects localhost / blank URLs
        # outright with 400 "Invalid success url", so until the public
        # URL is https we omit them: the hosted page shows Speed's own
        # success screen, and the paid webhook still flips the order —
        # the customer just isn't bounced back to /order/{token} yet.
        if settings.public_site_url.startswith("https://"):
            # Cancel lands on the order page too: it shows PAYMENT_PENDING
            # and the customer can re-attempt; sending them back to a cart
            # they already emptied would just confuse.
            payload["success_url"] = f"{settings.public_site_url}/order/{order.access_token}"
            payload["cancel_url"] = f"{settings.public_site_url}/order/{order.access_token}"

        with _client() as client:
            response = client.post(
                f"{settings.speed_api_base.rstrip('/')}/checkout-sessions",
                headers=_auth_headers(api_key),
                json=payload,
            )
        # Docs example shows 200; the official plugin asserts 201. Accept
        # either — both carry the session object.
        if response.status_code not in (200, 201):
            raise SpeedError(
                f"Speed checkout-session creation failed ({response.status_code}): {response.text[:300]}"
            )
        session = response.json()

        session_id = session.get("id")
        checkout_url = session.get("default_url") or session.get("url")
        if not session_id or not checkout_url:
            raise SpeedError(f"Speed response missing session id or hosted URL: {str(session)[:300]}")

        return PaymentInstructions(
            provider=self.provider_key,
            summary="Pay with Bitcoin — Lightning or on-chain",
            details={
                "provider_payment_id": session_id,
                "checkout_url": checkout_url,
                "usd_total_cents": order.total_cents,
                "expires_in_seconds": _SESSION_TTL_SECONDS,
            },
        )

    # -- webhook verification --------------------------------------------

    def verify_webhook(self, headers: dict[str, str], raw_body: bytes) -> VerifiedEvent:
        """Verify the HMAC signature and parse the event envelope. Any
        failure raises — app/api/webhooks.py turns that into a 400 and
        never calls handle_event."""
        secret = _require_webhook_secret()

        # Starlette passes headers case-insensitively but as a plain
        # dict here — normalize before reading the three required ones.
        norm = {k.lower(): v for k, v in headers.items()}
        signature_header = norm.get("webhook-signature")
        timestamp = norm.get("webhook-timestamp")
        msg_id = norm.get("webhook-id")
        if not signature_header or not timestamp or not msg_id:
            raise SpeedError("Missing webhook-signature / webhook-timestamp / webhook-id header.")

        expected = compute_expected_signature(secret, msg_id, timestamp, raw_body)

        # The header can carry several space-separated "v1,<sig>"
        # candidates (future signature versions) — accept if ANY matches.
        matched = False
        for candidate in signature_header.split(" "):
            candidate = candidate.strip()
            if not candidate:
                continue
            _, _, sig = candidate.partition(",")
            if sig and hmac.compare_digest(sig, expected):
                matched = True
                break
        if not matched:
            raise SpeedError("Webhook signature does not match the request.")

        try:
            body = json.loads(raw_body)
            event_type = body["event_type"]
            session_id = body["data"]["object"]["id"]
            event_id = body["id"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise SpeedError(f"Unparseable webhook body: {exc}") from exc

        # external_id = the envelope's event id (evt_...), which is the
        # identity of the EVENT and stable across retried deliveries.
        # The webhook-id header (msg_...) is per-delivery and changes on
        # every retry, so it must NOT be the idempotency key here —
        # WebhookEvent's UNIQUE(source, external_id) dedupes retries.
        return VerifiedEvent(
            external_id=event_id,
            event_type=event_type,
            order_id=None,  # resolved against the Payment row in handle_event
            raw=body,
        )

    # -- verified event handling ------------------------------------------

    def handle_event(self, session: Session, event: VerifiedEvent) -> None:
        """Map a verified checkout-session event onto the existing
        order-state transitions. Does not commit — app/api/webhooks.py
        owns the transaction boundary, same as every other caller."""
        obj = event.raw["data"]["object"]
        session_id = obj.get("id")
        payment = session.execute(
            select(Payment).where(Payment.provider_payment_id == session_id)
        ).scalar_one_or_none()
        if payment is None:
            # Session we didn't create (or a stale delivery for a payment
            # row that was cleaned up). Nothing to transition.
            logger.warning("Speed webhook for unknown checkout session %s — ignored.", session_id)
            return

        if event.event_type == "checkout_session.paid":
            # Defense in depth: the signature already proves Speed sent
            # this, but a session whose amount disagrees with our ledger
            # (cross-talk, provider bug) must never mark the order paid.
            expected_amount = round(payment.amount_cents / 100, 2)
            try:
                paid_amount = float(obj.get("amount"))
            except (TypeError, ValueError):
                logger.error("Speed session %s paid event has no numeric amount — not marking paid.", session_id)
                return
            if abs(paid_amount - expected_amount) > _AMOUNT_TOLERANCE:
                logger.error(
                    "Speed session %s paid %s but our Payment row expects %s — not marking paid.",
                    session_id,
                    paid_amount,
                    expected_amount,
                )
                return
            payment_services.mark_order_paid(
                session,
                order_id=payment.order_id,
                provider=self.provider_key,
                provider_payment_id=session_id,
                source="speed:webhook",
            )
        elif event.event_type == "checkout_session.payment_paid":
            # Partial payment (on-chain underpay awaiting confirmations /
            # tolerance). The session only flips to `.paid` when it's
            # whole — wait for that event instead of guessing here.
            logger.info("Speed session %s partially paid — waiting for checkout_session.paid.", session_id)
        else:
            # checkout_session.created / .deactivated / anything new
            # Speed adds: no state transition in v1.
            logger.info("Speed session %s event %s — no state transition.", session_id, event.event_type)
