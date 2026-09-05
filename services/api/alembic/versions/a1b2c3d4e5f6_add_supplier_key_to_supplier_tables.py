"""add supplier_key to supplier_products and mappings

The AllianceTek middleware serves two disjoint pharmacy catalogs behind
two tokens ("umsrx" = pens & pre-constituted, "nxgen" = lyophilized
vials), and product ids are only unique WITHIN a supplier. The catalog
sync, matching, and order push therefore need to know which supplier a
supplier_products row (and a mapping) belongs to.

supplier_products.supplier_key defaults to 'umsrx' (the legacy
single-token sync's supplier) and is backfilled to 'nxgen' for rows
whose id does not exist in the current umsrx catalog — a safe inference
only because the two catalogs are disjoint and both were synced before
this migration runs. supplier_product_mappings.supplier_key is
backfilled from the mapped supplier_products row.

Revision ID: a1b2c3d4e5f6
Revises: f4102e8c33e1
Create Date: 2026-08-28 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = 'f4102e8c33e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'supplier_products',
        sa.Column('supplier_key', sa.String(20), nullable=False, server_default='umsrx'),
    )
    op.add_column(
        'supplier_product_mappings',
        sa.Column('supplier_key', sa.String(20), nullable=False, server_default='umsrx'),
    )
    # Backfill: any synced row whose id is absent from the umsrx catalog
    # must be nxgen (the catalogs are disjoint). Runs only when both
    # catalogs are present in the table; a fresh single-supplier install
    # simply leaves everything at the default.
    op.execute(
        """
        UPDATE supplier_products sp
        SET supplier_key = 'nxgen'
        WHERE NOT EXISTS (
            SELECT 1 FROM supplier_products other
            WHERE other.supplier_product_id = sp.supplier_product_id
              AND other.supplier_key = 'umsrx'
        )
        AND EXISTS (
            SELECT 1 FROM supplier_products other
            WHERE other.supplier_key = 'umsrx'
        )
        """
    )
    op.execute(
        """
        UPDATE supplier_product_mappings m
        SET supplier_key = sp.supplier_key
        FROM supplier_products sp
        WHERE sp.supplier_product_id = m.supplier_product_id
        """
    )


def downgrade() -> None:
    op.drop_column('supplier_product_mappings', 'supplier_key')
    op.drop_column('supplier_products', 'supplier_key')
