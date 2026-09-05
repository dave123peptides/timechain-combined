"""add content to products

Structured research/informational copy for the PDP (overview, key
research highlights, research-area bullets, pairs-well-with cross-sell
slugs, FAQ) — modeled on realpeptides.co's product-page depth, per
David's 2026-08-24 direction. Lives on Product (not ProductVariant) since
it's the same across every strength of a compound.

Nullable JSONB, defaults to {} — existing rows render with no extra
sections until app.scripts.sync_product_content backfills them.

Revision ID: f4102e8c33e1
Revises: 2e0069fd4366
Create Date: 2026-08-24 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f4102e8c33e1'
down_revision: str | None = '2e0069fd4366'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    op.drop_column('products', 'content')
