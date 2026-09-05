from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog_import.matching import classify_match
from app.constants.forms import FORM_LABEL as _FORM_LABEL
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping
from app.models.events import AuditEvent


class AdminActionError(RuntimeError):
    """Raised when an admin action can't be completed (e.g. enabling a
    variant with no verified mapping, or referencing an id that doesn't
    exist). The route layer maps this to an HTTP 400 with the message
    shown directly to the admin."""


@dataclass(frozen=True)
class AdminProductRow:
    variant_id: uuid.UUID
    timechain_product: str
    format: str
    strength: Optional[str]
    wholesale_cost_cents: Optional[int]
    retail_price_cents: int
    sellable: bool
    supplier_product_id: Optional[int]
    supplier_sku: Optional[str]
    supplier_name: Optional[str]
    confidence: Optional[str]
    mapping_status: str  # "MAPPED" | "CHANGED" | "MISSING" | "UNMAPPED"


@dataclass(frozen=True)
class SupplierProductOption:
    supplier_product_id: int
    supplier_sku: str
    supplier_name: str


def _get_mappings(session: Session, variant_id: uuid.UUID) -> list[SupplierProductMapping]:
    """Always queries fresh rather than reading `variant.supplier_mappings`
    — that relationship gets cached in the session's identity map on
    first access, and a mapping added later via a raw FK assignment
    (as set_mapping does) doesn't retroactively appear in an
    already-loaded collection without an explicit refresh. A direct
    query sidesteps that staleness entirely."""
    return list(
        session.execute(
            select(SupplierProductMapping).where(SupplierProductMapping.product_variant_id == variant_id)
        ).scalars()
    )


def _pick_active_mapping(mappings: list[SupplierProductMapping]) -> Optional[SupplierProductMapping]:
    """The mapping currently backing sellability, if any. A variant can
    have more than one mapping row (history, or fallback suppliers via
    priority) — only a MAPPED-and-active one counts as "the" mapping."""
    for mapping in mappings:
        if mapping.mapping_status == "MAPPED" and mapping.is_active:
            return mapping
    return None


def _pick_latest_non_mapped(mappings: list[SupplierProductMapping]) -> Optional[SupplierProductMapping]:
    candidates = [mapping for mapping in mappings if not (mapping.mapping_status == "MAPPED" and mapping.is_active)]
    if not candidates:
        return None
    return max(candidates, key=lambda mapping: mapping.updated_at)


def _write_audit(session: Session, *, actor: str, action: str, entity_id: uuid.UUID, data: dict) -> None:
    session.add(
        AuditEvent(actor=actor, action=action, entity_type="product_variant", entity_id=entity_id, data=data)
    )
    # SessionLocal is configured with autoflush=False (see app/db/session.py),
    # so without this, the audit row wouldn't be visible to a query run
    # later in the same session/request until something else flushed.
    session.flush()


def list_admin_products(session: Session) -> list[AdminProductRow]:
    """One row per ProductVariant. A MAPPED variant shows its persisted
    mapping directly (cheap, always correct). Everything else — never
    mapped, or a mapping that's CHANGED/MISSING — gets a live
    classify_match() suggestion against the *current* supplier catalog,
    so the admin always sees an up-to-date candidate to act on rather
    than a stale snapshot from whenever the price sheet was last
    imported.
    """
    variants = list(
        session.execute(select(ProductVariant).join(Product).order_by(Product.name, ProductVariant.name)).scalars()
    )
    supplier_products = list(session.execute(select(SupplierProduct)).scalars())

    all_mappings = list(session.execute(select(SupplierProductMapping)).scalars())
    mappings_by_variant: dict[uuid.UUID, list[SupplierProductMapping]] = {}
    for mapping in all_mappings:
        mappings_by_variant.setdefault(mapping.product_variant_id, []).append(mapping)

    rows: list[AdminProductRow] = []
    for variant in variants:
        mappings = mappings_by_variant.get(variant.id, [])
        active = _pick_active_mapping(mappings)

        if active is not None:
            rows.append(
                AdminProductRow(
                    variant_id=variant.id,
                    timechain_product=variant.name,
                    format=_FORM_LABEL.get(variant.form or "", variant.form or "—"),
                    strength=variant.size_key,
                    wholesale_cost_cents=variant.wholesale_cost_cents,
                    retail_price_cents=variant.retail_price_cents,
                    sellable=variant.is_sellable,
                    supplier_product_id=active.supplier_product_id,
                    supplier_sku=active.supplier_sku,
                    supplier_name=active.supplier_name,
                    confidence=active.match_confidence,
                    mapping_status="MAPPED",
                )
            )
            continue

        latest = _pick_latest_non_mapped(mappings)
        # A row whose *persisted* status is still literally "MAPPED" but
        # is no longer active isn't a sync-detected CHANGED/MISSING — an
        # admin deliberately unmapped it. Show that as UNMAPPED, not the
        # stale "MAPPED" label, or "unmap" would look like it did nothing.
        if latest is None or latest.mapping_status == "MAPPED":
            mapping_status = "UNMAPPED"
        else:
            mapping_status = latest.mapping_status

        confidence = None
        candidate_id = candidate_sku = candidate_name = None
        if variant.form:
            result = classify_match(
                product_name=variant.name,
                size_key=variant.size_key,
                form=variant.form,
                supplier_products=supplier_products,
            )
            confidence = result.status
            if result.best is not None:
                candidate_id = result.best.supplier_product_id
                candidate_sku = result.best.supplier_sku
                candidate_name = result.best.supplier_name

        rows.append(
            AdminProductRow(
                variant_id=variant.id,
                timechain_product=variant.name,
                format=_FORM_LABEL.get(variant.form or "", variant.form or "—"),
                strength=variant.size_key,
                wholesale_cost_cents=variant.wholesale_cost_cents,
                retail_price_cents=variant.retail_price_cents,
                sellable=variant.is_sellable,
                supplier_product_id=candidate_id,
                supplier_sku=candidate_sku,
                supplier_name=candidate_name,
                confidence=confidence,
                mapping_status=mapping_status,
            )
        )
    return rows


def list_supplier_product_options(session: Session) -> list[SupplierProductOption]:
    """Every supplier product, for the "change mapping" picker."""
    supplier_products = session.execute(
        select(SupplierProduct).order_by(SupplierProduct.supplier_name)
    ).scalars()
    return [
        SupplierProductOption(
            supplier_product_id=sp.supplier_product_id, supplier_sku=sp.supplier_sku, supplier_name=sp.supplier_name
        )
        for sp in supplier_products
    ]


def set_mapping(
    session: Session, *, variant_id: uuid.UUID, supplier_product_id: int, actor: str, action_label: str
) -> SupplierProductMapping:
    """Shared implementation for both "approve" and "change": point
    variant_id's mapping at supplier_product_id, mapping_status=MAPPED.
    `action_label` only controls the audit action name
    ("mapping.approved" vs "mapping.changed") — the effect is identical,
    since both mean the same thing: an admin has just verified this link.
    """
    variant = session.get(ProductVariant, variant_id)
    if variant is None:
        raise AdminActionError(f"No such product variant: {variant_id}")

    supplier_product = session.execute(
        select(SupplierProduct).where(SupplierProduct.supplier_product_id == supplier_product_id)
    ).scalar_one_or_none()
    if supplier_product is None:
        raise AdminActionError(f"No such supplier product: {supplier_product_id}")

    previous_mapping = _pick_active_mapping(_get_mappings(session, variant_id))
    previous_supplier_product_id = previous_mapping.supplier_product_id if previous_mapping else None

    # What confidence tier justifies this specific pair? MANUAL if the
    # admin picked something other than the algorithm's own top
    # suggestion. Must classify against every supplier product, not just
    # this one — a single-candidate list would trivially make it "best"
    # by default regardless of how poor the match actually is.
    confidence = "MANUAL"
    if variant.form:
        all_supplier_products = list(session.execute(select(SupplierProduct)).scalars())
        result = classify_match(
            product_name=variant.name,
            size_key=variant.size_key,
            form=variant.form,
            supplier_products=all_supplier_products,
        )
        if result.best is not None and result.best.supplier_product_id == supplier_product_id:
            confidence = result.status

    mapping = session.execute(
        select(SupplierProductMapping).where(
            SupplierProductMapping.product_variant_id == variant_id,
            SupplierProductMapping.supplier_product_id == supplier_product_id,
        )
    ).scalar_one_or_none()
    if mapping is not None:
        mapping.supplier_sku = supplier_product.supplier_sku
        mapping.supplier_name = supplier_product.supplier_name
        mapping.supplier_key = supplier_product.supplier_key
        mapping.is_active = True
        mapping.mapping_status = "MAPPED"
        mapping.match_confidence = confidence
    else:
        mapping = SupplierProductMapping(
            product_variant_id=variant_id,
            supplier_product_id=supplier_product_id,
            supplier_key=supplier_product.supplier_key,
            supplier_sku=supplier_product.supplier_sku,
            supplier_name=supplier_product.supplier_name,
            priority=0,
            is_active=True,
            mapping_status="MAPPED",
            match_confidence=confidence,
        )
        session.add(mapping)

    # A variant has exactly one active mapping through this UI — if a
    # different supplier was previously active, it's superseded, not
    # deleted (keeps history, matches the FK's RESTRICT-not-delete design
    # used everywhere else in this schema).
    if previous_mapping is not None and previous_mapping.supplier_product_id != supplier_product_id:
        previous_mapping.is_active = False

    session.flush()
    _write_audit(
        session,
        actor=actor,
        action=action_label,
        entity_id=variant_id,
        data={
            "previous_supplier_product_id": previous_supplier_product_id,
            "new_supplier_product_id": supplier_product_id,
            "match_confidence": confidence,
        },
    )
    return mapping


def unmap(session: Session, *, variant_id: uuid.UUID, actor: str) -> None:
    variant = session.get(ProductVariant, variant_id)
    if variant is None:
        raise AdminActionError(f"No such product variant: {variant_id}")

    active = _pick_active_mapping(_get_mappings(session, variant_id))
    if active is None:
        raise AdminActionError("This variant has no active mapping to remove.")

    previous_supplier_product_id = active.supplier_product_id
    active.is_active = False
    # Same reactive-revocation pattern as sync reconciliation: removing
    # the mapping must not leave a stale is_sellable=True sitting there.
    variant.is_sellable = False
    session.flush()
    _write_audit(
        session,
        actor=actor,
        action="mapping.unmapped",
        entity_id=variant_id,
        data={"previous_supplier_product_id": previous_supplier_product_id},
    )


def enable(session: Session, *, variant_id: uuid.UUID, actor: str) -> ProductVariant:
    """Fails via ProductVariant._validate_is_sellable if there's no
    verified MAPPED mapping — the rule lives once, at the model layer,
    not duplicated here."""
    variant = session.get(ProductVariant, variant_id)
    if variant is None:
        raise AdminActionError(f"No such product variant: {variant_id}")
    try:
        variant.is_sellable = True
    except ValueError as exc:
        raise AdminActionError(str(exc)) from exc
    session.flush()
    _write_audit(session, actor=actor, action="variant.enabled", entity_id=variant_id, data={})
    return variant


def disable(session: Session, *, variant_id: uuid.UUID, actor: str) -> ProductVariant:
    variant = session.get(ProductVariant, variant_id)
    if variant is None:
        raise AdminActionError(f"No such product variant: {variant_id}")
    variant.is_sellable = False
    session.flush()
    _write_audit(session, actor=actor, action="variant.disabled", entity_id=variant_id, data={})
    return variant
