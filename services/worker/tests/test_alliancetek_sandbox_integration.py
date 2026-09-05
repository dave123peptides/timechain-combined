"""Sandbox integration test for AllianceTek order submission.

Uses the exact fixture supplied for this integration:
  supplier productId = 25688246
  supplier SKU        = "234"
  supplier exact name = "Test Sku"
  fake order number    = "TEST-TIMECHAIN-001"

This runs against an httpx.MockTransport, not a live network call — no
real AllianceTek sandbox credentials/URLs are configured in this dev
environment (SUPPLIER_API_ORDERS_URL etc. are blank; see .env.example).
Once real sandbox credentials exist, this same fixture data can be
replayed against the live sandbox as a follow-up. This test still proves
the exact outgoing payload shape end-to-end (payload builder -> client),
and structurally guards against ever pointing at a production URL.

Run with `-v -s` to see the captured sanitized request/response printed:
    docker compose exec worker python -m pytest \\
        tests/test_alliancetek_sandbox_integration.py -v -s
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from worker.alliancetek.client import AllianceTekClient
from worker.alliancetek.payload import build_order_payload

_SANDBOX_ORDERS_URL = "https://sandbox.alliancetek.example.invalid/orders"

_ORDER = {
    "public_order_number": "TEST-TIMECHAIN-001",
    "created_at": datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc),
    "shipping_address": {
        "line1": "1 Sandbox Way",
        "line2": None,
        "city": "Testville",
        "region": "CA",
        "postal_code": "90210",
        "country": "US",
    },
}

_ITEM = {
    "supplier_product_id_at_purchase": 25688246,
    "supplier_sku_at_purchase": "234",
    "supplier_name_at_purchase": "Test Sku",
    "quantity": 1,
    "unit_price_cents": 4900,
}


def test_sandbox_order_submission_payload_shape_and_sanitized_capture(capsys):
    assert "production" not in _SANDBOX_ORDERS_URL.lower(), "this test must never point at a production URL"

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        # Sanitized: capture the body only, never request.headers (that's
        # where X-Email/X-Api-Token live — see AllianceTekClient's
        # docstring on never logging _headers).
        captured["request_body"] = request.content.decode("utf-8")
        response_body = {
            "result": {
                "orderNumber": "TEST-TIMECHAIN-001",
                "orderStatus": "awaiting_shipment",
                "orderId": 555001,
            }
        }
        captured["response_body"] = response_body
        return httpx.Response(200, json=response_body)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = AllianceTekClient(
        orders_url=_SANDBOX_ORDERS_URL,
        email="sandbox-test@example.invalid",
        api_token="sandbox-test-token",
        environment="local",  # never "production"
        http_client=http_client,
    )

    order_payload = build_order_payload(_ORDER, [_ITEM])
    try:
        response = client.create_update_order(order_payload)
    finally:
        client.close()

    # --- exact outgoing payload shape ---
    assert order_payload["orderNumber"] == "TEST-TIMECHAIN-001"
    assert order_payload["orderStatus"] == "awaiting_shipment"
    assert order_payload["items"] == [
        {"sku": "234", "name": "Test Sku", "quantity": 1, "unitPrice": 49.00}
    ]

    # --- request actually sent ---
    assert captured["method"] == "POST"
    assert captured["url"] == _SANDBOX_ORDERS_URL
    assert '"orderNumber":"TEST-TIMECHAIN-001"' in captured["request_body"].replace(" ", "")
    assert "X-Api-Token" not in captured["request_body"]
    assert "X-Email" not in captured["request_body"]

    # --- response parsed correctly ---
    assert response == captured["response_body"]

    print("\n--- sandbox integration: sanitized request ---")
    print(f"{captured['method']} {captured['url']}")
    print(captured["request_body"])
    print("--- sandbox integration: sanitized response ---")
    print(captured["response_body"])

    out = capsys.readouterr().out
    assert "sandbox-test-token" not in out
    assert "sandbox-test@example.invalid" not in out
