"""ORDERING_ENABLED (David, 2026-10-22): the combined storefront shows the
catalog and books meetings; it never takes an order. These pin the API
side of that: with the switch off, both checkout writes refuse before
touching the database, while the catalog endpoints keep answering."""

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app

client = TestClient(app)

_QUOTE = {"items": [{"variant_id": "00000000-0000-0000-0000-000000000000", "quantity": 1}], "country": "US"}


def test_switch_defaults_off():
    assert Settings(_env_file=None).ordering_enabled is False


def test_quote_refused_when_ordering_disabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "ordering_enabled", False)
    response = client.post("/api/v1/checkout/quote", json=_QUOTE)
    assert response.status_code == 503
    assert "contact us" in response.json()["detail"].lower()


def test_create_refused_when_ordering_disabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "ordering_enabled", False)
    response = client.post(
        "/api/v1/checkout/create",
        json={
            **_QUOTE,
            "email": "lab@example.com",
            "customer_name": "Test Lab",
            "customer_phone": "3055550100",
            "shipping_address": {
                "line1": "1 Main St",
                "city": "Miami",
                "region": "FL",
                "postal_code": "33101",
                "country": "US",
            },
            "consent": {"age_confirmed": True, "ruo_acknowledged": True, "terms_accepted": True},
            "payment_method": "zelle",
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"].startswith("Ordering through this site is not available")


def test_catalog_still_served_when_ordering_disabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "ordering_enabled", False)
    assert client.get("/shop/products").status_code == 200
    assert client.get("/shop/filter-options").status_code == 200
