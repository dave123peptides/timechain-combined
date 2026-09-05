"""supplier fulfillment pipeline: order item snapshots, supplier_orders redesign, background_jobs

Revision ID: 2e0069fd4366
Revises: 9790d30bac00
Create Date: 2026-08-12 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2e0069fd4366'
down_revision: str | None = '9790d30bac00'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # order_items: rename name_snapshot -> display_name_at_purchase, add
    # the supplier-identity and wholesale-cost snapshot columns. Table is
    # empty (no orders have shipped yet), so nullable=False is safe with
    # no backfill.
    op.alter_column('order_items', 'name_snapshot', new_column_name='display_name_at_purchase')
    op.add_column('order_items', sa.Column('supplier_product_id_at_purchase', sa.BigInteger(), nullable=False))
    op.add_column('order_items', sa.Column('supplier_sku_at_purchase', sa.Text(), nullable=False))
    op.add_column('order_items', sa.Column('supplier_name_at_purchase', sa.Text(), nullable=False))
    op.add_column('order_items', sa.Column('wholesale_cost_cents', sa.Integer(), nullable=True))

    # supplier_orders: drop the singular supplier_product_id FK (AllianceTek
    # submits one orderNumber with an items array per TimeChain order, not
    # one submission per product) in favor of supplier_order_number +
    # provider. Table is empty, so this is a design correction, not data
    # loss.
    op.drop_constraint(
        op.f('fk_supplier_orders_supplier_product_id_supplier_products'), 'supplier_orders', type_='foreignkey'
    )
    op.drop_index(op.f('ix_supplier_orders_supplier_product_id'), table_name='supplier_orders')
    op.drop_column('supplier_orders', 'supplier_product_id')
    op.add_column('supplier_orders', sa.Column('supplier_order_number', sa.String(length=50), nullable=False))
    op.add_column(
        'supplier_orders',
        sa.Column('provider', sa.String(length=50), server_default='alliancetek', nullable=False),
    )
    op.alter_column('supplier_orders', 'cost_cents', existing_type=sa.Integer(), nullable=True)

    op.create_table(
        'background_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='pending', nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_background_jobs')),
    )
    op.create_index(op.f('ix_background_jobs_job_type'), 'background_jobs', ['job_type'], unique=False)
    # The worker's receive() filters on status='pending' AND available_at <=
    # now() every poll — a partial index on exactly that predicate keeps
    # the SKIP LOCKED scan cheap as the table grows.
    op.create_index(
        'ix_background_jobs_pending_available',
        'background_jobs',
        ['available_at'],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index('ix_background_jobs_pending_available', table_name='background_jobs')
    op.drop_index(op.f('ix_background_jobs_job_type'), table_name='background_jobs')
    op.drop_table('background_jobs')

    op.alter_column('supplier_orders', 'cost_cents', existing_type=sa.Integer(), nullable=False)
    op.drop_column('supplier_orders', 'provider')
    op.drop_column('supplier_orders', 'supplier_order_number')
    op.add_column(
        'supplier_orders', sa.Column('supplier_product_id', postgresql.UUID(as_uuid=True), nullable=False)
    )
    op.create_index(
        op.f('ix_supplier_orders_supplier_product_id'), 'supplier_orders', ['supplier_product_id'], unique=False
    )
    op.create_foreign_key(
        op.f('fk_supplier_orders_supplier_product_id_supplier_products'),
        'supplier_orders',
        'supplier_products',
        ['supplier_product_id'],
        ['id'],
        ondelete='RESTRICT',
    )

    op.drop_column('order_items', 'wholesale_cost_cents')
    op.drop_column('order_items', 'supplier_name_at_purchase')
    op.drop_column('order_items', 'supplier_sku_at_purchase')
    op.drop_column('order_items', 'supplier_product_id_at_purchase')
    op.alter_column('order_items', 'display_name_at_purchase', new_column_name='name_snapshot')
