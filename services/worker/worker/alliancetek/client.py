from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger("timechain.worker.alliancetek")


class SupplierApiConfigError(RuntimeError):
    """Raised when required supplier API configuration is missing."""


class SupplierApiError(RuntimeError):
    """Raised when the supplier API can't be reached or returns an
    unexpected response shape."""


@dataclass(frozen=True)
class SupplierProductsPage:
    page: int
    pages: int
    total: int
    products: list[dict[str, Any]]


def _parse_products_page(payload: Any) -> SupplierProductsPage:
    try:
        result = payload["result"]
        return SupplierProductsPage(
            page=int(result["page"]),
            pages=int(result["pages"]),
            total=int(result["total"]),
            products=list(result["products"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        top_level_keys = sorted(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
        raise SupplierApiError(
            "Unexpected supplier API response shape; expected result.page/pages/total/products. "
            f"Top-level keys seen: {top_level_keys}"
        ) from exc


class AllianceTekClient:
    """Client for the AllianceTek Sandbox/Production API (ShipStation
    custom-store-API shaped — see SupplierProduct's docstring).

    Auth is via the `X-Email` / `X-Api-Token` headers, supplied only
    through environment variables — never hardcoded, and never logged
    (`_headers` is never passed to a logger anywhere in this class).

    Sandbox and Production are isolated primarily by which URLs/
    credentials this instance is constructed with — a deployment loads
    exactly one settings object (sandbox locally, production in AWS), so
    the two are never mixed in the same process. The one deliberate
    exception is `get_tracking_records`: AllianceTek surfaces tracking
    data via a different endpoint per environment (Fulfillments in
    Sandbox, Shipments in Production), so this class accepts an
    `environment` string and makes that one routing decision internally
    — the only place in the whole app allowed to branch on environment
    for tracking, so it never gets scattered into callers like
    refresh_tracking.py.

    `create_update_order`/`get_order`/`list_fulfillments`/
    `list_shipments` return the raw parsed JSON body rather than a typed
    shape — unlike `list_products`, AllianceTek's exact response shape
    for these hasn't been confirmed yet (only the products endpoint has
    been verified against the real sandbox). Callers should treat the
    return value defensively until that's confirmed.
    """

    def __init__(
        self,
        *,
        products_url: str = "",
        orders_url: str = "",
        order_status_url: str = "",
        fulfillments_url: str = "",
        shipments_url: str = "",
        email: str,
        api_token: str,
        environment: str = "local",
        supplier_key: str = "umsrx",
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        if not email or not api_token:
            raise SupplierApiConfigError(
                "SUPPLIER_API_EMAIL and SUPPLIER_API_TOKEN must both be set via environment "
                "variables before the AllianceTek client can authenticate."
            )
        self._products_url = products_url
        self._orders_url = orders_url
        self._order_status_url = order_status_url
        self._fulfillments_url = fulfillments_url
        self._shipments_url = shipments_url
        self._environment = environment
        # Which pharmacy account this client talks to; stamped onto synced
        # supplier_products rows by supplier_sync.
        self.supplier_key = supplier_key
        # Never pass this dict to a logger.
        self._headers = {"X-Email": email, "X-Api-Token": api_token}
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._client = http_client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = http_client is None

    @classmethod
    def from_settings(cls, settings: Any) -> "AllianceTekClient":
        """Builds a client from a worker Settings object — the one place
        job handlers should construct an AllianceTekClient, so every
        handler ends up pointed at the same URLs/credentials/timeouts
        rather than each hand-rolling its own construction call."""
        return cls(
            products_url=settings.supplier_api_products_url,
            orders_url=settings.supplier_api_orders_url,
            order_status_url=settings.supplier_api_order_status_url,
            fulfillments_url=settings.supplier_api_fulfillments_url,
            shipments_url=settings.supplier_api_shipments_url,
            email=settings.supplier_api_email,
            api_token=settings.supplier_api_token,
            environment=settings.environment,
            timeout_seconds=settings.supplier_api_timeout_seconds,
            max_retries=settings.supplier_api_max_retries,
        )

    @classmethod
    def from_settings_for_supplier(cls, settings: Any, supplier_key: str) -> "AllianceTekClient":
        """Like from_settings but with the token for one pharmacy account.

        Token resolution: SUPPLIER_<KEY>_API_TOKEN if set, else the legacy
        SUPPLIER_API_TOKEN for the default supplier ("umsrx"), else a
        config error naming the missing variable.
        """
        per_key = getattr(settings, f"supplier_{supplier_key}_api_token", "")
        if per_key:
            token = per_key
        elif supplier_key == "umsrx" and settings.supplier_api_token:
            token = settings.supplier_api_token
        else:
            raise SupplierApiConfigError(
                f"SUPPLIER_{supplier_key.upper()}_API_TOKEN must be set via environment "
                "variables to sync that supplier's catalog."
            )
        return cls(
            products_url=settings.supplier_api_products_url,
            orders_url=settings.supplier_api_orders_url,
            order_status_url=settings.supplier_api_order_status_url,
            fulfillments_url=settings.supplier_api_fulfillments_url,
            shipments_url=settings.supplier_api_shipments_url,
            email=settings.supplier_api_email,
            api_token=token,
            environment=settings.environment,
            supplier_key=supplier_key,
            timeout_seconds=settings.supplier_api_timeout_seconds,
            max_retries=settings.supplier_api_max_retries,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "AllianceTekClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _request(self, description: str, request: Callable[[], httpx.Response]) -> httpx.Response:
        """Shared retry/backoff loop for every endpoint below. `request`
        is called fresh on each attempt (httpx requests aren't
        replayable). Only the exception class name is ever logged — never
        the request/response objects, which could echo `_headers`."""
        last_error: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info("alliancetek: %s (attempt %s)", description, attempt)
                response = request()
                response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == self._max_retries:
                    break
                sleep_seconds = self._retry_backoff_seconds * attempt
                logger.warning(
                    "alliancetek: %s failed (%s), retrying in %.1fs",
                    description,
                    exc.__class__.__name__,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)

        assert last_error is not None
        raise SupplierApiError(f"Failed to {description} after {self._max_retries} attempts") from last_error

    def list_products(self, page: int) -> SupplierProductsPage:
        if not self._products_url:
            raise SupplierApiConfigError(
                "SUPPLIER_API_PRODUCTS_URL is not configured. Set it via environment variable."
            )
        response = self._request(
            f"list products page {page}",
            lambda: self._client.get(self._products_url, params={"page": page}, headers=self._headers),
        )
        return _parse_products_page(response.json())

    def create_update_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Submits (or, on retry, re-submits) an order. AllianceTek
        confirmed `orderNumber` is idempotent — the same value updates
        the existing supplier order rather than creating a duplicate, so
        callers must always pass the same `orderNumber` for retries of
        the same TimeChain order (see
        worker/jobs/submit_supplier_order.py)."""
        if not self._orders_url:
            raise SupplierApiConfigError(
                "SUPPLIER_API_ORDERS_URL is not configured. Set it via environment variable."
            )
        order_number = payload.get("orderNumber", "?")
        response = self._request(
            f"create/update order {order_number}",
            lambda: self._client.post(self._orders_url, json=payload, headers=self._headers),
        )
        return response.json()

    def get_order(self, order_number: str) -> dict[str, Any]:
        if not self._order_status_url:
            raise SupplierApiConfigError(
                "SUPPLIER_API_ORDER_STATUS_URL is not configured. Set it via environment variable."
            )
        response = self._request(
            f"get order {order_number}",
            lambda: self._client.get(
                self._order_status_url, params={"orderNumber": order_number}, headers=self._headers
            ),
        )
        return response.json()

    def list_fulfillments(self, order_number: str) -> dict[str, Any]:
        if not self._fulfillments_url:
            raise SupplierApiConfigError(
                "SUPPLIER_API_FULFILLMENTS_URL is not configured. Set it via environment variable."
            )
        response = self._request(
            f"list fulfillments for order {order_number}",
            lambda: self._client.get(
                self._fulfillments_url, params={"orderNumber": order_number}, headers=self._headers
            ),
        )
        return response.json()

    def list_shipments(self, order_number: str) -> dict[str, Any]:
        if not self._shipments_url:
            raise SupplierApiConfigError(
                "SUPPLIER_API_SHIPMENTS_URL is not configured. Set it via environment variable."
            )
        response = self._request(
            f"list shipments for order {order_number}",
            lambda: self._client.get(
                self._shipments_url, params={"orderNumber": order_number}, headers=self._headers
            ),
        )
        return response.json()

    def get_tracking_records(self, order_number: str) -> dict[str, Any]:
        """Confirmed AllianceTek behavior: Sandbox surfaces tracking via
        Fulfillments, Production via Shipments. This is the one place
        that distinction is allowed to exist — callers (e.g.
        refresh_tracking.py) call this and never think about which
        underlying endpoint was used, so the environment check never gets
        scattered elsewhere in the app."""
        if self._environment == "production":
            return self.list_shipments(order_number)
        return self.list_fulfillments(order_number)
