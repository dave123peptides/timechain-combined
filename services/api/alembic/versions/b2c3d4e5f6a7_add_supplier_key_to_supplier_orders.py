"""add supplier_key to supplier_orders

Which pharmacy account (umsrx / nxgen) an order was pushed to, resolved
at push time from the mapped supplier_products row backing the order's
items. Tracking refresh and order reconciliation read it back so they
talk to the same pharmacy the order went to. Nullable: pre-dual-supplier
orders and non-AllianceTek providers carry NULL and fall back to the
legacy default client.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-28 00:10:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('supplier_orders', sa.Column('supplier_key', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('supplier_orders', 'supplier_key')
