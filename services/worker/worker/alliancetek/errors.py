from __future__ import annotations

import httpx

from worker.alliancetek.client import SupplierApiConfigError, SupplierApiError

# 429/500/502/503/504 plus connect/read timeouts and generic transport
# failures are treated as transient — worth retrying. Everything else
# (4xx validation errors: bad SKU, bad supplier name, invalid payload,
# auth error, invalid address) is permanent — retrying won't fix bad data,
# so those go straight to MANUAL_REVIEW instead of looping forever.
TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Delay before each successive retry attempt: immediate, 30s, 2m, 10m, 30m.
# Index 0 is the delay before the first retry (i.e. immediately after the
# first failure), index 1 before the second retry, etc. Once this list is
# exhausted, submit_supplier_order gives up and routes to MANUAL_REVIEW.
RETRY_DELAYS_SECONDS: list[int] = [0, 30, 120, 600, 1800]


class SupplierErrorClass:
    TRANSIENT = "transient"
    PERMANENT = "permanent"


def classify_supplier_error(exc: Exception) -> str:
    """Transient vs. permanent, for deciding whether a supplier-call
    failure is worth retrying.

    AllianceTekClient._request wraps every failure in
    SupplierApiError(...) from <original httpx exception> — this unwraps
    __cause__ to classify against the real exception rather than needing
    the client's raise shape to change. SupplierApiConfigError (a URL
    isn't configured) is also permanent: retrying won't make a blank
    setting appear, but it does need a human, so it still routes to
    MANUAL_REVIEW rather than looping forever.

    AllianceTek's exact error-response shape for 4xx validation failures
    (bad SKU vs. bad address vs. auth error, etc.) hasn't been confirmed
    against the real API yet, so classification here is coarse — transient
    iff the status code is one of the five listed above, permanent for
    every other status and for anything unclassifiable. The raw response
    is always preserved in supplier_attempts.response_data so a human can
    see exactly what AllianceTek said, rather than this function guessing
    wrong about which specific validation problem occurred.
    """
    if isinstance(exc, SupplierApiConfigError):
        return SupplierErrorClass.PERMANENT

    cause = exc.__cause__ if isinstance(exc, SupplierApiError) else exc

    if isinstance(cause, httpx.HTTPStatusError):
        if cause.response.status_code in TRANSIENT_STATUS_CODES:
            return SupplierErrorClass.TRANSIENT
        return SupplierErrorClass.PERMANENT

    if isinstance(cause, httpx.TimeoutException):
        # Covers both connect timeout and read timeout.
        return SupplierErrorClass.TRANSIENT

    if isinstance(cause, httpx.TransportError):
        # Generic temporary network failure (DNS, connection reset, etc.).
        return SupplierErrorClass.TRANSIENT

    # Unknown/unclassified — default to permanent rather than looping
    # forever on something we don't understand.
    return SupplierErrorClass.PERMANENT
