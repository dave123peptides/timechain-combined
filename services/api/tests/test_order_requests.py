"""Order requests (David, 2026-10-22): the site's one conversion. These
cover the service's validation and snapshot, the public endpoint, the
honeypot, the CRM payload shape, and the admin listing's auth."""

from __future__ import annotations

import base64
import itertools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping
from app.models.order_requests import OrderRequest
from app.services import order_requests

client = TestClient(app)

_TEST_SLUG_PREFIX = "test-order-request"
_TEST_EMAIL = "requests-test@example.com"
_supplier_ids = itertools.count(998_200)


def _cleanup(session):
    session.execute(text("DELETE FROM order_requests WHERE email = :email"), {"email": _TEST_EMAIL})
    session.execute(text("DELETE FROM products WHERE slug LIKE :prefix"), {"prefix": f"{_TEST_SLUG_PREFIX}%"})
    session.execute(text("DELETE FROM supplier_products WHERE supplier_product_id BETWEEN 998200 AND 998299"))
    session.commit()


@pytest.fixture
def session():
    db = SessionLocal()
    _cleanup(db)
    yield db
    db.rollback()
    _cleanup(db)
    db.close()


def _sellable_variant(session, suffix: str, *, form="pen", size_key="10", sellable=True):
    product = Product(slug=f"{_TEST_SLUG_PREFIX}-{suffix}", name=f"Test Compound {suffix}", images=[], is_active=True)
    session.add(product)
    session.flush()
    variant = ProductVariant(
        product_id=product.id,
        sku=f"TC-TEST-REQ-{suffix.upper()}",
        name=f"Test Compound {suffix} {size_key}mg",
        retail_price_cents=1000,
        form=form,
        size_key=size_key,
    )
    session.add(variant)
    session.flush()
    if sellable:
        supplier_id = next(_supplier_ids)
        supplier = SupplierProduct(
            supplier_product_id=supplier_id,
            supplier_sku=f"TEST-{supplier_id}",
            supplier_name="Test supplier row",
            supplier_active=True,
            raw_payload={"productId": supplier_id},
        )
        session.add(supplier)
        session.flush()
        session.add(
            SupplierProductMapping(
                product_variant_id=variant.id,
                supplier_product_id=supplier_id,
                supplier_sku=supplier.supplier_sku,
                supplier_name=supplier.supplier_name,
                mapping_status="MAPPED",
            )
        )
        session.flush()
        variant.is_sellable = True
    session.commit()
    session.refresh(variant)
    return variant


def _contact(**overrides):
    base = dict(name="Dana Lab", organization="Example Research LLC", email=_TEST_EMAIL)
    base.update(overrides)
    return order_requests.ContactInput(**base)


def test_create_snapshots_items_and_merges_duplicates(session):
    pen = _sellable_variant(session, "pen", form="pen")
    vial = _sellable_variant(session, "vial", form="lyophilized", size_key="20")
    request = order_requests.create_order_request(
        session,
        contact=_contact(phone=" 305 555 0100 ", notes="Quarterly stock"),
        items=[
            order_requests.RequestedItem(pen.id, 10),
            order_requests.RequestedItem(vial.id, 5),
            order_requests.RequestedItem(pen.id, 15),
        ],
    )
    assert request.reference.startswith("REQ-") and len(request.reference) == 10
    assert request.status == "NEW"
    assert request.phone == "305 555 0100"
    by_sku = {item["sku"]: item for item in request.items}
    assert by_sku[pen.sku]["quantity"] == 25
    assert by_sku[vial.sku] == {
        "variant_id": str(vial.id),
        "sku": vial.sku,
        "product_slug": f"{_TEST_SLUG_PREFIX}-vial",
        "product_name": "Test Compound vial",
        "variant_name": "Test Compound vial 20mg",
        "form": "lyophilized",
        "form_label": "Lyophilized",
        "strength": "20",
        "quantity": 5,
    }
    # No price anywhere in the snapshot.
    assert not any("price" in key for item in request.items for key in item)


def test_create_rejects_unsellable_variant_and_writes_nothing(session):
    hidden = _sellable_variant(session, "hidden", sellable=False)
    with pytest.raises(order_requests.OrderRequestError, match="no longer available"):
        order_requests.create_order_request(session, contact=_contact(), items=[order_requests.RequestedItem(hidden.id, 1)])
    assert session.query(OrderRequest).filter(OrderRequest.email == _TEST_EMAIL).count() == 0


def test_create_rejects_missing_contact_fields(session):
    pen = _sellable_variant(session, "contact")
    with pytest.raises(order_requests.OrderRequestError, match="required"):
        order_requests.create_order_request(
            session, contact=_contact(organization="  "), items=[order_requests.RequestedItem(pen.id, 1)]
        )


def test_webhook_payload_is_flat_and_names_the_items(session):
    pen = _sellable_variant(session, "payload", form="pen", size_key="10")
    request = order_requests.create_order_request(
        session, contact=_contact(name="Dana Lab", role="Practice manager"), items=[order_requests.RequestedItem(pen.id, 12)]
    )
    payload = order_requests.webhook_payload(request)
    assert payload["event"] == "order_request.created"
    assert payload["first_name"] == "Dana" and payload["last_name"] == "Lab"
    assert payload["organization"] == "Example Research LLC"
    assert payload["item_count"] == 1 and payload["unit_count"] == 12
    assert payload["items_text"] == "Test Compound payload, 10mg, Pen x 12"
    assert payload["items"][0]["sku"] == pen.sku


def test_forward_posts_to_configured_url(monkeypatch):
    calls = []

    class _Response:
        status_code = 200

    def fake_post(url, json, timeout):
        calls.append((url, json))
        return _Response()

    monkeypatch.setattr(order_requests.httpx, "post", fake_post)
    assert order_requests.forward_order_request({"reference": "REQ-TEST"}, url="https://hooks.example.test/wf") is True
    assert calls == [("https://hooks.example.test/wf", {"reference": "REQ-TEST"})]
    # Blank URL: nothing sent, nothing raised.
    monkeypatch.setattr(get_settings(), "order_request_webhook_url", "")
    assert order_requests.forward_order_request({"reference": "REQ-TEST"}) is False


def test_endpoint_creates_and_answers_with_reference(session, monkeypatch):
    sent = []
    monkeypatch.setattr(order_requests, "forward_order_request", lambda payload, url=None: sent.append(payload) or True)
    pen = _sellable_variant(session, "endpoint")
    response = client.post(
        "/api/v1/order-requests",
        json={
            "name": "Dana Lab",
            "organization": "Example Research LLC",
            "email": _TEST_EMAIL,
            "items": [{"variant_id": str(pen.id), "quantity": 30}],
            "source_path": "/shop/bpc-157",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["reference"].startswith("REQ-")
    assert sent and sent[0]["reference"] == body["reference"]
    stored = session.query(OrderRequest).filter(OrderRequest.reference == body["reference"]).one()
    assert stored.source_path == "/shop/bpc-157"


def test_endpoint_honeypot_drops_silently(session):
    pen = _sellable_variant(session, "honeypot")
    response = client.post(
        "/api/v1/order-requests",
        json={
            "name": "Bot",
            "organization": "Bot Inc",
            "email": _TEST_EMAIL,
            "website": "http://spam.example",
            "items": [{"variant_id": str(pen.id), "quantity": 1}],
        },
    )
    assert response.status_code == 201
    assert response.json()["reference"] == "REQ-RECEIVED"
    assert session.query(OrderRequest).filter(OrderRequest.email == _TEST_EMAIL).count() == 0


def test_endpoint_rejects_bad_quantity_and_unknown_variant(session):
    pen = _sellable_variant(session, "bad")
    base = {"name": "Dana", "organization": "Org", "email": _TEST_EMAIL}
    assert client.post("/api/v1/order-requests", json={**base, "items": [{"variant_id": str(pen.id), "quantity": 0}]}).status_code == 422
    response = client.post(
        "/api/v1/order-requests",
        json={**base, "items": [{"variant_id": "00000000-0000-0000-0000-000000000000", "quantity": 1}]},
    )
    assert response.status_code == 400
    assert "no longer available" in response.json()["detail"]


def test_admin_listing_requires_auth_and_lists_newest_first(session, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_basic_auth_user", "admin")
    monkeypatch.setattr(get_settings(), "admin_basic_auth_password", "secret")
    assert client.get("/admin/order-requests").status_code == 401
    pen = _sellable_variant(session, "admin")
    first = order_requests.create_order_request(session, contact=_contact(), items=[order_requests.RequestedItem(pen.id, 1)])
    second = order_requests.create_order_request(session, contact=_contact(), items=[order_requests.RequestedItem(pen.id, 2)])
    auth = base64.b64encode(b"admin:secret").decode()
    response = client.get("/admin/order-requests", headers={"Authorization": f"Basic {auth}"})
    assert response.status_code == 200
    refs = [row["reference"] for row in response.json() if row["email"] == _TEST_EMAIL]
    assert refs[:2] == [second.reference, first.reference]
    assert response.json()[0]["items"][0]["quantity"] == 2
