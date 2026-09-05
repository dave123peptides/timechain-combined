from __future__ import annotations

import logging

import httpx
import pytest

from worker.alliancetek.client import AllianceTekClient, SupplierApiConfigError, SupplierApiError

_EMAIL = "test@example.com"
_TOKEN = "super-secret-token"


def _client(handler, **kwargs) -> AllianceTekClient:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return AllianceTekClient(email=_EMAIL, api_token=_TOKEN, http_client=http_client, **kwargs)


# ---------------------------------------------------------------------------
# create_update_order
# ---------------------------------------------------------------------------


def test_create_update_order_posts_payload_with_auth_headers():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["email_header"] = request.headers.get("X-Email")
        captured["token_header"] = request.headers.get("X-Api-Token")
        return httpx.Response(200, json={"result": {"orderId": 42}})

    client = _client(handler, orders_url="https://sandbox.example.invalid/orders")
    try:
        result = client.create_update_order({"orderNumber": "TCP-ABC123", "items": []})
    finally:
        client.close()

    assert captured["method"] == "POST"
    assert captured["url"] == "https://sandbox.example.invalid/orders"
    assert captured["email_header"] == _EMAIL
    assert captured["token_header"] == _TOKEN
    assert result == {"result": {"orderId": 42}}


def test_create_update_order_requires_orders_url_configured():
    client = _client(lambda request: httpx.Response(200, json={}))
    try:
        with pytest.raises(SupplierApiConfigError):
            client.create_update_order({"orderNumber": "TCP-X"})
    finally:
        client.close()


# ---------------------------------------------------------------------------
# get_order
# ---------------------------------------------------------------------------


def test_get_order_sends_order_number_as_query_param():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"result": {"orderStatus": "shipped"}})

    client = _client(handler, order_status_url="https://sandbox.example.invalid/order-status")
    try:
        result = client.get_order("TCP-ABC123")
    finally:
        client.close()

    assert captured["params"] == {"orderNumber": "TCP-ABC123"}
    assert result == {"result": {"orderStatus": "shipped"}}


def test_get_order_requires_order_status_url_configured():
    client = _client(lambda request: httpx.Response(200, json={}))
    try:
        with pytest.raises(SupplierApiConfigError):
            client.get_order("TCP-X")
    finally:
        client.close()


# ---------------------------------------------------------------------------
# list_fulfillments / list_shipments
# ---------------------------------------------------------------------------


def test_list_fulfillments_sends_order_number_and_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert dict(request.url.params) == {"orderNumber": "TCP-ABC123"}
        return httpx.Response(200, json={"result": {"fulfillments": []}})

    client = _client(handler, fulfillments_url="https://sandbox.example.invalid/fulfillments")
    try:
        result = client.list_fulfillments("TCP-ABC123")
    finally:
        client.close()
    assert result == {"result": {"fulfillments": []}}


def test_list_fulfillments_requires_url_configured():
    client = _client(lambda request: httpx.Response(200, json={}))
    try:
        with pytest.raises(SupplierApiConfigError):
            client.list_fulfillments("TCP-X")
    finally:
        client.close()


def test_list_shipments_sends_order_number_and_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert dict(request.url.params) == {"orderNumber": "TCP-ABC123"}
        return httpx.Response(200, json={"result": {"shipments": []}})

    client = _client(handler, shipments_url="https://sandbox.example.invalid/shipments")
    try:
        result = client.list_shipments("TCP-ABC123")
    finally:
        client.close()
    assert result == {"result": {"shipments": []}}


def test_list_shipments_requires_url_configured():
    client = _client(lambda request: httpx.Response(200, json={}))
    try:
        with pytest.raises(SupplierApiConfigError):
            client.list_shipments("TCP-X")
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Retry/backoff shared across every method, and the never-log-credentials
# guarantee.
# ---------------------------------------------------------------------------


def test_create_update_order_retries_then_raises_after_exhausting_attempts():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(500, json={"error": "boom"})

    client = _client(
        handler, orders_url="https://sandbox.example.invalid/orders", max_retries=2, retry_backoff_seconds=0.0
    )
    try:
        with pytest.raises(SupplierApiError):
            client.create_update_order({"orderNumber": "TCP-X"})
    finally:
        client.close()

    assert call_count["n"] == 2


def test_client_never_logs_credentials(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = _client(
        handler, orders_url="https://sandbox.example.invalid/orders", max_retries=2, retry_backoff_seconds=0.0
    )
    try:
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(SupplierApiError):
                client.create_update_order({"orderNumber": "TCP-X"})
    finally:
        client.close()

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert _TOKEN not in log_text
    assert _EMAIL not in log_text


# ---------------------------------------------------------------------------
# get_tracking_records — sandbox routes to Fulfillments, production to
# Shipments. This is the only place that distinction is allowed to exist.
# ---------------------------------------------------------------------------


def test_get_tracking_records_uses_fulfillments_when_not_production():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "fulfillments" in str(request.url)
        return httpx.Response(200, json={"result": {"fulfillments": []}})

    client = _client(
        handler,
        fulfillments_url="https://sandbox.example.invalid/fulfillments",
        shipments_url="https://sandbox.example.invalid/shipments",
        environment="local",
    )
    try:
        result = client.get_tracking_records("TCP-ABC123")
    finally:
        client.close()
    assert result == {"result": {"fulfillments": []}}


def test_get_tracking_records_uses_shipments_in_production():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "shipments" in str(request.url)
        return httpx.Response(200, json={"result": {"shipments": []}})

    client = _client(
        handler,
        fulfillments_url="https://sandbox.example.invalid/fulfillments",
        shipments_url="https://sandbox.example.invalid/shipments",
        environment="production",
    )
    try:
        result = client.get_tracking_records("TCP-ABC123")
    finally:
        client.close()
    assert result == {"result": {"shipments": []}}


def test_get_tracking_records_defaults_to_sandbox_behavior_when_environment_unset():
    """The safe default: anything other than the literal "production"
    string (local/dev/staging/unset) uses Fulfillments, matching "do not
    call Production" caution elsewhere in this integration."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert "fulfillments" in str(request.url)
        return httpx.Response(200, json={"result": {}})

    client = _client(
        handler,
        fulfillments_url="https://sandbox.example.invalid/fulfillments",
        shipments_url="https://sandbox.example.invalid/shipments",
    )
    try:
        client.get_tracking_records("TCP-ABC123")
    finally:
        client.close()
