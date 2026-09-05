"""rename order_number to public_order_number; PAYMENT_PENDING default

Formalizing checkout into POST /api/v1/checkout/{quote,create}:
- order_number -> public_order_number, matching the field name the
  customer-facing checkout API actually returns, and making explicit
  (via the name itself) that this — never orders.id — is what's ever
  shown to a customer. Format changes from "TC-<10 hex chars>" to
  "TCP-<6 human-friendly chars>" (e.g. "TCP-A74K9P") — see
  app.services.storefront._generate_public_order_number.
- status now defaults to "PAYMENT_PENDING" (was "pending") — the literal
  value POST /api/v1/checkout/create sets on every new order.

orders has 0 rows as of this migration — plain rename/default change,
no data migration needed.

Revision ID: 9790d30bac00
Revises: 5f8e0c58a306
Create Date: 2026-08-13 10:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9790d30bac00'
down_revision: str | None = '5f8e0c58a306'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column('orders', 'order_number', new_column_name='public_order_number')
    op.execute('ALTER INDEX ix_orders_order_number RENAME TO ix_orders_public_order_number')
    op.alter_column(
        'orders', 'status',
        existing_type=sa.String(length=30),
        server_default='PAYMENT_PENDING',
    )


def downgrade() -> None:
    op.alter_column(
        'orders', 'status',
        existing_type=sa.String(length=30),
        server_default='pending',
    )
    op.execute('ALTER INDEX ix_orders_public_order_number RENAME TO ix_orders_order_number')
    op.alter_column('orders', 'public_order_number', new_column_name='order_number')
