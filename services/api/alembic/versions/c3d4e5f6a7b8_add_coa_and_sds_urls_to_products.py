"""add coa_url and sds_url to products

Public document links (supplier Certificate of Analysis / Safety Data
Sheet PDFs) surfaced as buttons on the PDP and listed centrally on
/coa. Lives on Product rather than ProductVariant: a COA covers the
compound and lot, not an individual strength SKU.

Both nullable, and NULL is a meaningful state rather than missing data —
no third-party lab documents exist for this catalog yet, so the frontend
renders an honest "COA available on request" empty state. That empty
state is deliberate: fabricating a purity figure or an unverifiable
"tested" badge is the exact regulatory exposure this column is meant to
retire, not create. Text rather than String(n) since these are external
URLs of unbounded length.

Affects 0 rows: both columns land NULL for all 72 existing products, and
stay NULL until real PDFs arrive from UMS-RX / NxGen.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-30 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: str | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('products', sa.Column('coa_url', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('sds_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'sds_url')
    op.drop_column('products', 'coa_url')
