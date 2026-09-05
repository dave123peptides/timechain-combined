from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Connection

# Mirrors the minimal columns needed from services/api's
# supplier_product_mappings / product_variants tables — same
# hand-kept-in-sync pattern as supplier_products_table in db.py, and for
# the same reason (no shared code layer between the two services).
metadata = sa.MetaData()

supplier_product_mappings_table = sa.Table(
    "supplier_product_mappings",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("product_variant_id", UUID(as_uuid=True), nullable=False),
    sa.Column("supplier_product_id", sa.BigInteger, nullable=False),
    sa.Column("supplier_key", sa.String(20), nullable=False),
    sa.Column("mapping_status", sa.String(20), nullable=False),
)

product_variants_table = sa.Table(
    "product_variants",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("is_sellable", sa.Boolean, nullable=False),
)


@dataclass(frozen=True)
class ReconciliationResult:
    mappings_marked_changed: int
    mappings_marked_missing: int
    variants_deactivated: int


def get_mapped_supplier_product_ids(conn: Connection, supplier_key: str) -> set[int]:
    """Every supplier_product_id currently backing a MAPPED mapping for
    one supplier — used by sync.py to work out which of them didn't show
    up in this run's (validated-complete) fetch of THAT supplier, i.e.
    have disappeared. Scoped per supplier: a product mapped from nxgen
    must not be judged against an umsrx fetch (and vice versa)."""
    result = conn.execute(
        sa.select(supplier_product_mappings_table.c.supplier_product_id).where(
            supplier_product_mappings_table.c.mapping_status == "MAPPED",
            supplier_product_mappings_table.c.supplier_key == supplier_key,
        )
    )
    return {row.supplier_product_id for row in result}


def _downgrade_mappings(
    conn: Connection, supplier_product_ids: list[int], *, new_status: str, supplier_key: str
) -> list:
    """MAPPED -> new_status for the given supplier_product_ids of one
    supplier only — already-downgraded mappings are left alone
    (idempotent). Returns the affected product_variant_ids."""
    if not supplier_product_ids:
        return []
    stmt = (
        supplier_product_mappings_table.update()
        .where(
            supplier_product_mappings_table.c.supplier_product_id.in_(supplier_product_ids),
            supplier_product_mappings_table.c.supplier_key == supplier_key,
            supplier_product_mappings_table.c.mapping_status == "MAPPED",
        )
        .values(mapping_status=new_status)
        .returning(supplier_product_mappings_table.c.product_variant_id)
    )
    return [row.product_variant_id for row in conn.execute(stmt)]


def reconcile_mapping_drift(
    conn: Connection,
    *,
    changed_supplier_product_ids: list[int],
    disappeared_supplier_product_ids: list[int],
    supplier_key: str,
) -> ReconciliationResult:
    """Reacts to supplier data that invalidates an approved mapping.

    Only ever *revokes* — moves a mapping MAPPED -> CHANGED/MISSING and
    forces its variant's is_sellable to False. Never creates a mapping,
    never sets is_sellable to True, and never moves a mapping back to
    MAPPED — that's app.services.mapping_status.approve_mapping()'s job,
    a deliberate admin action, not something a sync run ever does.
    """
    changed_variant_ids = _downgrade_mappings(
        conn, changed_supplier_product_ids, new_status="CHANGED", supplier_key=supplier_key
    )
    missing_variant_ids = _downgrade_mappings(
        conn, disappeared_supplier_product_ids, new_status="MISSING", supplier_key=supplier_key
    )

    affected_variant_ids = list({*changed_variant_ids, *missing_variant_ids})
    variants_deactivated = 0
    if affected_variant_ids:
        stmt = (
            product_variants_table.update()
            .where(
                product_variants_table.c.id.in_(affected_variant_ids),
                product_variants_table.c.is_sellable.is_(True),
            )
            .values(is_sellable=False)
            .returning(product_variants_table.c.id)
        )
        variants_deactivated = len(list(conn.execute(stmt)))

    return ReconciliationResult(
        mappings_marked_changed=len(changed_variant_ids),
        mappings_marked_missing=len(missing_variant_ids),
        variants_deactivated=variants_deactivated,
    )
