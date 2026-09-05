"""add admin_products support columns

For the /admin/products admin page: product_variants.size_key/form let
the admin service run classify_match() live for unmapped variants
without reverse-parsing name/sku; supplier_product_mappings.
match_confidence records why a mapping was made (EXACT from import,
or the tier an admin knowingly approved, or MANUAL for an override).

All 77 existing mappings were created by catalog_import as EXACT
matches, so defaulting match_confidence to 'EXACT' is a correct
backfill, not a placeholder. size_key/form are left NULL on existing
rows — backfilled by re-running `python -m app.catalog_import.run`.

Revision ID: 45fe22784570
Revises: 375253fb84d5
Create Date: 2026-08-12 10:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45fe22784570'
down_revision: str | None = '375253fb84d5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('product_variants', sa.Column('size_key', sa.String(length=50), nullable=True))
    op.add_column('product_variants', sa.Column('form', sa.String(length=20), nullable=True))
    op.add_column(
        'supplier_product_mappings',
        sa.Column('match_confidence', sa.String(length=20), server_default='EXACT', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('supplier_product_mappings', 'match_confidence')
    op.drop_column('product_variants', 'form')
    op.drop_column('product_variants', 'size_key')
