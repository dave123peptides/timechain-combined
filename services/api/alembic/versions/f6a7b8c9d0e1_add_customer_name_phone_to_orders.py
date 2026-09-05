"""add customer_name and customer_phone to orders

Launch fulfillment is manual (David, 9/4): the customer pays by Venmo or
Zelle, and David places the order with the supplier himself once the
transfer arrives. That needs the full customer record on the order —
the name the parcel is addressed to and a phone number — neither of
which the order carried before (email + street address only). Both
nullable so existing orders are untouched; checkout requires both from
here on.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-04 22:30:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: str | None = 'e5f6a7b8c9d0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('customer_name', sa.String(length=200), nullable=True))
    op.add_column('orders', sa.Column('customer_phone', sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'customer_phone')
    op.drop_column('orders', 'customer_name')
