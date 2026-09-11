"""Add provider_data JSONB column to payments table.

Stores hosted-checkout payment details (OpenNode lightning invoice,
chain address, bitcoin URI, sats amount, expiry, checkout URL) so the
order page can show the payment itself on every visit, not just the
checkout response. Null for manual-transfer methods (venmo/zelle/ach).

Ported from the Timechain repo (David, 2026-09-11).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c94eb8909d1a"
down_revision: Union[str, None] = "b2c3d4e5f6a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("provider_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payments", "provider_data")
