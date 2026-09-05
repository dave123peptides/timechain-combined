from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

metadata = sa.MetaData()

# Mirrors the `supplier_products` table defined by services/api's Alembic
# migrations. Defined here rather than imported because services/api and
# services/worker are separately deployed containers with no shared code
# layer today — if that changes, this should be replaced with a shared
# package import instead of hand-kept-in-sync columns.
supplier_products_table = sa.Table(
    "supplier_products",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("supplier_product_id", sa.BigInteger, nullable=False, unique=True),
    sa.Column("supplier_key", sa.String(20), nullable=False, server_default="umsrx"),
    sa.Column("supplier_sku", sa.Text, nullable=False),
    sa.Column("supplier_name", sa.Text, nullable=False),
    sa.Column("supplier_active", sa.Boolean, nullable=False),
    sa.Column("supplier_price_cents", sa.Integer, nullable=True),
    sa.Column("raw_payload", JSONB, nullable=False),
    sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)


_COMPARE_COLUMNS = (
    "supplier_sku",
    "supplier_name",
    "supplier_active",
    "supplier_price_cents",
    "raw_payload",
)

# Narrower than _COMPARE_COLUMNS above: only these three identify *which*
# product a mapping points at. A price change doesn't invalidate an
# approved mapping; a rename, re-SKU, or deactivation does — see
# reconciliation.py, which reacts only to changes in this set.
_IDENTITY_COLUMNS = ("supplier_sku", "supplier_name", "supplier_active")


@dataclass(frozen=True)
class UpsertResult:
    inserted: int
    updated: int
    unchanged: int
    changed_identity_ids: list[int]


def upsert_supplier_products(
    conn: Connection, rows: list[dict[str, Any]], *, now: datetime
) -> UpsertResult:
    """Upserts rows into `supplier_products`, keyed on `supplier_product_id`.

    This function only ever writes to `supplier_products`. It never
    touches `products`, `product_variants`, or `supplier_product_mappings`
    — syncing the supplier catalog must never automatically make anything
    sellable on the storefront. That mapping is a separate, deliberate
    step done elsewhere.

    Classifies each row as inserted / updated / unchanged by snapshotting
    the pre-upsert state of any matching rows first, then comparing —
    `last_seen_at` (and `updated_at`) are bumped on every sync regardless,
    but a row only counts as "updated" if its supplier-owned fields
    actually differ from what was already stored.
    """
    if not rows:
        return UpsertResult(inserted=0, updated=0, unchanged=0, changed_identity_ids=[])

    ids = [row["supplier_product_id"] for row in rows]
    existing_by_id: dict[int, dict[str, Any]] = {}
    select_stmt = sa.select(
        supplier_products_table.c.supplier_product_id, *(supplier_products_table.c[col] for col in _COMPARE_COLUMNS)
    ).where(supplier_products_table.c.supplier_product_id.in_(ids))
    for existing_row in conn.execute(select_stmt).mappings():
        existing_by_id[existing_row["supplier_product_id"]] = dict(existing_row)

    values = [
        {
            **row,
            "first_seen_at": now,
            "last_seen_at": now,
            "created_at": now,
            "updated_at": now,
        }
        for row in rows
    ]

    stmt = pg_insert(supplier_products_table).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[supplier_products_table.c.supplier_product_id],
        set_={
            "supplier_key": stmt.excluded.supplier_key,
            "supplier_sku": stmt.excluded.supplier_sku,
            "supplier_name": stmt.excluded.supplier_name,
            "supplier_active": stmt.excluded.supplier_active,
            "supplier_price_cents": stmt.excluded.supplier_price_cents,
            "raw_payload": stmt.excluded.raw_payload,
            "last_seen_at": stmt.excluded.last_seen_at,
            "updated_at": stmt.excluded.updated_at,
            # first_seen_at / created_at intentionally omitted so existing
            # rows keep their original values across re-syncs.
        },
    )
    conn.execute(stmt)

    inserted = updated = unchanged = 0
    changed_identity_ids: list[int] = []
    for row in rows:
        previous = existing_by_id.get(row["supplier_product_id"])
        if previous is None:
            inserted += 1
        elif any(previous[col] != row[col] for col in _COMPARE_COLUMNS):
            updated += 1
            if any(previous[col] != row[col] for col in _IDENTITY_COLUMNS):
                changed_identity_ids.append(row["supplier_product_id"])
        else:
            unchanged += 1

    return UpsertResult(
        inserted=inserted, updated=updated, unchanged=unchanged, changed_identity_ids=changed_identity_ids
    )
