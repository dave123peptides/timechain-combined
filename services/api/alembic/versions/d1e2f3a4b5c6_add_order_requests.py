"""Add order_requests: multi-quantity order requests from the storefront.

The combined site takes no payments (David, 2026-10-22). A requester
builds a list of compounds, formats, strengths and quantities and sends
it with their contact details; the request is stored here, forwarded to
the CRM webhook, and the order is arranged from there.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c94eb8909d1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reference", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="NEW", nullable=False),
        sa.Column("contact_name", sa.String(length=200), nullable=False),
        sa.Column("organization", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_path", sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_requests")),
    )
    op.create_index(op.f("ix_order_requests_reference"), "order_requests", ["reference"], unique=True)
    op.create_index(op.f("ix_order_requests_email"), "order_requests", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_order_requests_email"), table_name="order_requests")
    op.drop_index(op.f("ix_order_requests_reference"), table_name="order_requests")
    op.drop_table("order_requests")
