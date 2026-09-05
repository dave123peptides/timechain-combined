"""default product_variants.is_sellable to false

A variant must have a verified supplier mapping before it can be
sellable (see ProductVariant._validate_is_sellable) — defaulting the
column to True let any code path that omitted is_sellable in the
constructor bypass that check entirely, since column defaults are
applied at flush time, not through the validated attribute setter.

No existing row is changed: 0 rows currently have is_sellable=true, and
this only changes what new rows default to when the column is omitted.

Revision ID: cfa4110bc71d
Revises: 09cb48fa385e
Create Date: 2026-08-12 08:36:38.671067

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cfa4110bc71d'
down_revision: str | None = '09cb48fa385e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        'product_variants',
        'is_sellable',
        existing_type=sa.Boolean(),
        server_default=sa.text('false'),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'product_variants',
        'is_sellable',
        existing_type=sa.Boolean(),
        server_default=sa.text('true'),
        existing_nullable=False,
    )
