from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.models.orders import Order


@dataclass(frozen=True)
class PaymentInstructions:
    """What the checkout confirmation page needs to display so the
    customer can actually pay. Deliberately a loose `details` payload
    rather than a rigid schema — a crypto provider's instructions (asset,
    address, amount, QR payload) look nothing like ACH's (routing/account
    number, or a hosted-form redirect URL), and the exact shape depends
    on whichever vendor ends up integrated. `summary` is the one thing
    every provider can produce: a short human-readable line to show
    immediately, before/without needing to render `details` at all.
    """

    provider: str
    summary: str
    details: dict[str, Any]


@dataclass(frozen=True)
class VerifiedEvent:
    """The result of a provider verifying its own webhook signature —
    only handle_event() should ever see event data, and only after
    verify_webhook() has vouched for it."""

    external_id: str
    event_type: str
    order_id: str | None
    raw: dict[str, Any]


class PaymentProvider(Protocol):
    """The seam a real crypto or ACH integration plugs into. Nothing in
    this repo implements this yet — see registry.py. The shape is
    intentionally minimal: every provider must be able to (1) tell a
    customer how to pay, (2) prove a webhook is really from it, and
    (3) turn a verified event into a call against
    app.services.payments.mark_order_paid /
    mark_order_payment_failed — the same functions the interim
    admin-driven "mark as paid" action already calls (see
    app/services/admin_orders.py), so wiring in a real provider later
    only ever means implementing this interface, never touching the
    order-status state machine itself.
    """

    provider_key: str

    def create_payment_instructions(self, order: Order) -> PaymentInstructions:
        """Called right after an order is created, to build what the
        checkout confirmation page shows the customer."""
        ...

    def verify_webhook(self, headers: dict[str, str], raw_body: bytes) -> VerifiedEvent:
        """Verify the inbound webhook's signature and parse it into a
        VerifiedEvent. Must raise if verification fails — the caller
        (api/webhooks.py) never processes an event this didn't return
        successfully."""
        ...

    def handle_event(self, session: Session, event: VerifiedEvent) -> uuid.UUID | None:
        """Map a verified event to a call into
        app.services.payments.mark_order_paid / mark_order_payment_failed
        (or, eventually, a refund recorder). Does not commit — the
        caller's transaction boundary owns that, same as every other
        service function in this codebase.

        Returns the id of the order this event transitioned to PAID, or
        None when nothing became paid. api/webhooks.py uses the return
        value to schedule the post-payment fan-out
        (app/services/order_paid.py) after its commit."""
        ...
