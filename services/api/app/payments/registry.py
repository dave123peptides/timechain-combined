from __future__ import annotations

from app.payments.base import PaymentProvider

# Keyed by the same string stored in Payment.provider / used as the
# checkout `payment_method` field ("crypto", "ach").
#
# "crypto" is Speed (Bitcoin, Lightning + on-chain) — see
# app/payments/speed.py. Registration is unconditional and safe
# without an API key: the provider validates configuration lazily at
# call time (blank SPEED_API_KEY -> SpeedNotConfigured -> the checkout
# degrades gracefully), never at import time.
#
# "venmo", "zelle" and "ach" have no provider — those orders create fine
# and stay PAYMENT_PENDING until an admin confirms the transfer arrived
# (app.services.payments.mark_order_paid). Venmo and Zelle are the launch
# methods (David, 9/4); the customer sends the transfer themselves with
# the public order number as the memo.
from app.payments.speed import SpeedProvider

_PROVIDERS: dict[str, PaymentProvider] = {
    "crypto": SpeedProvider(),
}


def get_provider(key: str) -> PaymentProvider:
    provider = _PROVIDERS.get(key)
    if provider is None:
        raise NotImplementedError(
            f"No payment provider registered for {key!r} yet — see app/payments/registry.py."
        )
    return provider
