"""add shipping_address and access_token to orders

For the storefront checkout flow: shipping_address (JSONB) captures the
guest checkout form, access_token is the opaque unguessable value used
by the /order/[token] guest lookup page (deliberately distinct from
order_number, the human/support-facing reference).

orders is empty (0 rows) as of this migration, so access_token can be
added NOT NULL directly — no backfill needed.

Revision ID: 21f701e15635
Revises: 45fe22784570
Create Date: 2026-08-12 11:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '21f701e15635'
down_revision: str | None = '45fe22784570'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('access_token', sa.String(length=64), nullable=False))
    op.create_index(op.f('ix_orders_access_token'), 'orders', ['access_token'], unique=True)
    op.add_column('orders', sa.Column('shipping_address', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'shipping_address')
    op.drop_index(op.f('ix_orders_access_token'), table_name='orders')
    op.drop_column('orders', 'access_token')
