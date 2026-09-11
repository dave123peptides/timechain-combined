from __future__ import annotations

from app.payments.base import PaymentProvider

# Keyed by the same string stored in Payment.provider / used as the
# checkout `payment_method` field.
#
# "bitcoin_opennode" is OpenNode (Bitcoin, Lightning + on-chain, hosted
# checkout) — see app/payments/opennode.py. The live Bitcoin method
# since 2026-09-10 (David).
#
# "crypto" is Speed — see app/payments/speed.py. Dormant: the storefront
# no longer offers it, but the key stays registered so any historical
# "crypto" row (and its re-mint path) keeps working.
#
# Registration is unconditional and safe without API keys: each provider
# validates configuration lazily at call time (blank key →
# NotConfigured → the checkout degrades gracefully), never at import.
#
# "venmo", "zelle" and "ach" have no provider — those orders create fine
# and stay PAYMENT_PENDING until an admin confirms the transfer arrived
# (app.services.payments.mark_order_paid). Venmo and Zelle are manual
# transfers (David, 9/4); the customer sends the transfer themselves
# with the public order number as the memo.
from app.payments.opennode import OpenNodeProvider
from app.payments.speed import SpeedProvider

_PROVIDERS: dict[str, PaymentProvider] = {
    "bitcoin_opennode": OpenNodeProvider(),
    "crypto": SpeedProvider(),
}


def has_provider(key: str) -> bool:
    """True when `key` is a hosted-checkout method with a registered
    provider (as opposed to a manual transfer like venmo/zelle)."""
    return key in _PROVIDERS


def get_provider(key: str) -> PaymentProvider:
    provider = _PROVIDERS.get(key)
    if provider is None:
        raise NotImplementedError(
            f"No payment provider registered for {key!r} yet — see app/payments/registry.py."
        )
    return provider
