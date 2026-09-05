from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import SupplierProduct, SupplierProductMapping

MappingStatus = Literal["MAPPED", "CHANGED", "MISSING"]


def get_mapping_status(session: Session, product_variant_id: uuid.UUID) -> MappingStatus:
    """The current state of a variant's link to a supplier product. Exists
    to gate `ProductVariant.is_sellable` — see `_validate_is_sellable` in
    app/models/catalog.py.

    Reads the persisted, sticky `SupplierProductMapping.mapping_status`
    column directly — it does NOT recompute drift live. That detection
    happens once, reactively, in
    worker/supplier_sync/reconciliation.py, at sync time; recomputing it
    live here would let a mapping silently drift back to MAPPED the
    moment supplier data happened to realign, defeating "requires admin
    review before re-enabling."

    - MISSING: either no supplier_product_mappings row exists for this
      variant at all (covers every pre-mapping review state — LIKELY,
      AMBIGUOUS, NO_MATCH/UNMAPPED — none of those ever create a mapping
      row in the first place; see app/catalog_import/sync.py), or every
      existing mapping row's persisted status is itself `"MISSING"` (the
      supplier product disappeared from the feed — see
      worker/supplier_sync/reconciliation.py).
    - CHANGED: at least one mapping row exists, but none currently backs
      sellability — either its persisted status is `"CHANGED"`, or it's
      still `"MAPPED"` but manually deactivated (`is_active=False`).
    - MAPPED: at least one mapping row is `mapping_status="MAPPED"` AND
      `is_active=True`. A variant can have more than one supplier mapping
      (fallback suppliers via `priority`); one working link is enough.
    """
    mappings = list(
        session.execute(
            select(SupplierProductMapping).where(SupplierProductMapping.product_variant_id == product_variant_id)
        ).scalars()
    )
    if not mappings:
        return "MISSING"

    if any(mapping.mapping_status == "MAPPED" and mapping.is_active for mapping in mappings):
        return "MAPPED"
    if any(
        mapping.mapping_status == "CHANGED" or (mapping.mapping_status == "MAPPED" and not mapping.is_active)
        for mapping in mappings
    ):
        return "CHANGED"
    return "MISSING"


def get_active_mapping(session: Session, product_variant_id: uuid.UUID) -> SupplierProductMapping | None:
    """The mapping currently backing sellability for a single variant, if
    any — the same "MAPPED and active" rule as `get_mapping_status`, but
    returning the row itself rather than just its status. A variant can
    have more than one mapping row (history, or fallback suppliers via
    priority); only a MAPPED-and-active one counts as "the" mapping.

    Used by app/services/storefront.py to snapshot real supplier identity
    onto an OrderItem at purchase time — never call this from fulfillment
    code after an order exists, it reads live mapping state.
    """
    mappings = list(
        session.execute(
            select(SupplierProductMapping).where(SupplierProductMapping.product_variant_id == product_variant_id)
        ).scalars()
    )
    for mapping in mappings:
        if mapping.mapping_status == "MAPPED" and mapping.is_active:
            return mapping
    return None


def approve_mapping(session: Session, mapping: SupplierProductMapping) -> SupplierProductMapping:
    """The one explicit path back to MAPPED after reconciliation has
    marked a mapping CHANGED/MISSING. Never called by sync or catalog
    import — only ever by a deliberate admin action. Refreshes the
    snapshot to match live supplier data at approval time, since
    approving is itself a re-verification.
    """
    supplier_product = session.execute(
        select(SupplierProduct).where(SupplierProduct.supplier_product_id == mapping.supplier_product_id)
    ).scalar_one_or_none()
    if supplier_product is None:
        # Defensive: the FK is ON DELETE RESTRICT, so a mapped
        # supplier_products row can never actually be deleted while this
        # mapping references it — this should be unreachable in practice.
        raise ValueError(
            f"Cannot approve mapping {mapping.id}: supplier_product_id={mapping.supplier_product_id} "
            f"no longer exists in supplier_products."
        )

    mapping.supplier_sku = supplier_product.supplier_sku
    mapping.supplier_name = supplier_product.supplier_name
    mapping.supplier_key = supplier_product.supplier_key
    mapping.is_active = True
    mapping.mapping_status = "MAPPED"
    return mapping
