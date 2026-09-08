"""add discount_code and discount_cents to orders

Checkout discount codes (David, 9/6; first code NATALIE = 10% off).
The order snapshots the normalized code and the cents it took off the
subtotal; total_cents already reflects it. Nullable / zero-default so
existing orders read as "no discount".

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-09-06 01:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a8'
down_revision: str | None = 'f6a7b8c9d0e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('discount_code', sa.String(length=40), nullable=True))
    op.add_column('orders', sa.Column('discount_cents', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('orders', 'discount_cents')
    op.drop_column('orders', 'discount_code')
