"""Order requests (David, 2026-10-22): the combined site's replacement for
checkout. A requester builds a list of variants with quantities and
sends it with contact details; this stores the request as an immutable
snapshot and forwards it to the CRM webhook.

Validation is deliberately strict about the catalog and loose about the
person: every variant must be sellable right now (so the snapshot names
a real, current configuration) but the contact fields are whatever they
typed, trimmed. There is no price anywhere in a request.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants.forms import FORM_LABEL
from app.core.config import get_settings
from app.models.catalog import Product, ProductVariant
from app.models.order_requests import OrderRequest

logger = logging.getLogger(__name__)

_REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L
_WEBHOOK_TIMEOUT_SECONDS = 10.0
MAX_ITEMS = 50
MAX_QUANTITY = 10_000


class OrderRequestError(ValueError):
    """A problem with the request itself, worth a 400 with this message."""


@dataclass(frozen=True)
class RequestedItem:
    variant_id: uuid.UUID
    quantity: int


@dataclass(frozen=True)
class ContactInput:
    name: str
    organization: str
    email: str
    role: str | None = None
    phone: str | None = None
    region: str | None = None
    notes: str | None = None
    source_path: str | None = None


def _generate_reference() -> str:
    return "REQ-" + "".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(6))


def _clean(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text[:limit] if text else None


def _snapshot_items(session: Session, items: list[RequestedItem]) -> list[dict]:
    if not items:
        raise OrderRequestError("Add at least one item to the request.")
    if len(items) > MAX_ITEMS:
        raise OrderRequestError(f"A request can hold at most {MAX_ITEMS} lines.")
    # Merge duplicate variants rather than rejecting them: two lines for
    # the same configuration is a UI accident, not a bad request.
    merged: dict[uuid.UUID, int] = {}
    for item in items:
        if item.quantity <= 0 or item.quantity > MAX_QUANTITY:
            raise OrderRequestError(f"Quantities must be between 1 and {MAX_QUANTITY}.")
        merged[item.variant_id] = min(MAX_QUANTITY, merged.get(item.variant_id, 0) + item.quantity)

    rows = session.execute(
        select(ProductVariant, Product)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(ProductVariant.id.in_(list(merged)), ProductVariant.is_sellable.is_(True))
    ).all()
    found = {variant.id: (variant, product) for variant, product in rows}
    missing = [str(variant_id) for variant_id in merged if variant_id not in found]
    if missing:
        raise OrderRequestError("One or more items are no longer available. Remove them and try again.")

    snapshot = []
    for variant_id, quantity in merged.items():
        variant, product = found[variant_id]
        snapshot.append(
            {
                "variant_id": str(variant.id),
                "sku": variant.sku,
                "product_slug": product.slug,
                "product_name": product.name,
                "variant_name": variant.name,
                "form": variant.form,
                "form_label": FORM_LABEL.get(variant.form or "", variant.form or ""),
                "strength": variant.size_key,
                "quantity": quantity,
            }
        )
    return snapshot


def create_order_request(session: Session, *, contact: ContactInput, items: list[RequestedItem]) -> OrderRequest:
    name = _clean(contact.name, 200)
    organization = _clean(contact.organization, 200)
    email = _clean(contact.email, 320)
    if not name or not organization or not email:
        raise OrderRequestError("Name, organization and email are required.")

    snapshot = _snapshot_items(session, items)

    request = OrderRequest(
        reference=_generate_reference(),
        contact_name=name,
        organization=organization,
        role=_clean(contact.role, 120),
        email=email,
        phone=_clean(contact.phone, 40),
        region=_clean(contact.region, 100),
        notes=_clean(contact.notes, 4000),
        items=snapshot,
        source_path=_clean(contact.source_path, 300),
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    logger.info("order request %s stored: %d lines for %s", request.reference, len(snapshot), organization)
    return request


def items_summary(items: list[dict]) -> str:
    """One line per item, for a CRM field or an email body:
    "BPC-157, 10mg, Pen x 25"."""
    lines = []
    for item in items:
        strength = item.get("strength")
        parts = [item.get("product_name") or item.get("variant_name") or item.get("sku") or "?"]
        if strength:
            parts.append(f"{strength}mg" if strength.replace(".", "").replace("/", "").isdigit() else strength)
        if item.get("form_label"):
            parts.append(item["form_label"])
        lines.append(f"{', '.join(parts)} x {item.get('quantity', 0)}")
    return "\n".join(lines)


def webhook_payload(request: OrderRequest) -> dict:
    """Flat keys so a GoHighLevel inbound-webhook mapper can bind them to
    contact fields; the items also ride along as a list for anything
    that can read JSON."""
    first_name, _, last_name = request.contact_name.partition(" ")
    return {
        "event": "order_request.created",
        "reference": request.reference,
        "email": request.email,
        "first_name": first_name,
        "last_name": last_name.strip(),
        "name": request.contact_name,
        "phone": request.phone or "",
        "organization": request.organization,
        "role": request.role or "",
        "region": request.region or "",
        "notes": request.notes or "",
        "item_count": len(request.items),
        "unit_count": sum(int(item.get("quantity", 0)) for item in request.items),
        "items_text": items_summary(request.items),
        "items": request.items,
        "source_path": request.source_path or "",
        "created_at": request.created_at.isoformat() if request.created_at else "",
    }


def forward_order_request(payload: dict, url: str | None = None) -> bool:
    """Fire-and-forget POST to the CRM webhook. Runs as a background task
    after the request is committed: any failure is logged and dropped,
    never surfaced to the requester (the request itself is already
    stored and visible in /admin/requests)."""
    url = (url if url is not None else get_settings().order_request_webhook_url).strip()
    if not url:
        return False
    try:
        response = httpx.post(url, json=payload, timeout=_WEBHOOK_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        logger.warning("order request %s webhook failed: %s", payload.get("reference"), exc)
        return False
    if response.status_code >= 400:
        logger.warning("order request %s webhook answered %s", payload.get("reference"), response.status_code)
        return False
    return True


def list_order_requests(session: Session, *, limit: int = 200) -> list[OrderRequest]:
    return list(
        session.execute(select(OrderRequest).order_by(OrderRequest.created_at.desc()).limit(limit)).scalars()
    )
