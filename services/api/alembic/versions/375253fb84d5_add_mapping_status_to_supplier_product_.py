"""add mapping_status to supplier_product_mappings

Persisted and sticky, not recomputed: MAPPED / CHANGED / MISSING. Backs
the reactive-unsellable rule — supplier sync downgrades this the moment
live supplier data drifts or the product disappears, and nothing
automated ever moves it back to MAPPED (see
app/services/mapping_status.py).

All 77 existing mapping rows are currently-valid EXACT-match mappings
created by the catalog import, so defaulting them to MAPPED reflects
their actual state, not a placeholder.

Revision ID: 375253fb84d5
Revises: cfa4110bc71d
Create Date: 2026-08-12 09:10:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '375253fb84d5'
down_revision: str | None = 'cfa4110bc71d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'supplier_product_mappings',
        sa.Column('mapping_status', sa.String(length=20), server_default='MAPPED', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('supplier_product_mappings', 'mapping_status')
