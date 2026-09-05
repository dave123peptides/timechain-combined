"""add product_coas; drop products.coa_url

Third-party Certificates of Analysis arrived for the catalog (Accumark
Labs reports for the supplier's lots — 241 of them across 30 compounds
on 2026-09-03). A product accumulates one certificate per lot per
strength, so they get their own table rather than a URL column: the
PDP's Lab report tab shows one card per strength with the latest
certificate and every earlier one behind it, and /coa lists them all.

products.coa_url is dropped in the same revision. It was added
(c3d4e5f6a7b8) as a single-document placeholder while no certificates
existed and was NULL for every row; keeping it alongside product_coas
would leave two places a "COA" could come from, which is how a stale
link outlives the certificate it pointed at. products.sds_url is
untouched — no SDS exists yet, and it stays a single document per
product.

Rows are loaded by app.scripts.sync_coas from data/coa/coa_manifest.csv
(see app.scripts.build_coa_manifest). This revision creates the table
empty.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-03 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: str | None = 'd4e5f6a7b8c9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'product_coas',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('verify_code', sa.String(length=20), nullable=False),
        sa.Column('strength', sa.String(length=50), nullable=True),
        sa.Column('lot', sa.Text(), nullable=False),
        sa.Column('issued_on', sa.Date(), nullable=False),
        sa.Column('lab', sa.Text(), nullable=False),
        sa.Column('client', sa.Text(), nullable=False),
        sa.Column('tests', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('pdf_url', sa.Text(), nullable=False),
        sa.Column('verify_url', sa.Text(), nullable=True),
        sa.Column('source_file', sa.Text(), nullable=True),
        sa.Column('is_published', sa.Boolean(), server_default='true', nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_product_coas_product_id'), 'product_coas', ['product_id'], unique=False)
    op.create_index(op.f('ix_product_coas_verify_code'), 'product_coas', ['verify_code'], unique=True)
    op.create_index(
        'ix_product_coas_product_strength_issued',
        'product_coas',
        ['product_id', 'strength', 'issued_on'],
        unique=False,
    )
    op.drop_column('products', 'coa_url')


def downgrade() -> None:
    op.add_column('products', sa.Column('coa_url', sa.Text(), nullable=True))
    op.drop_index('ix_product_coas_product_strength_issued', table_name='product_coas')
    op.drop_index(op.f('ix_product_coas_verify_code'), table_name='product_coas')
    op.drop_index(op.f('ix_product_coas_product_id'), table_name='product_coas')
    op.drop_table('product_coas')
