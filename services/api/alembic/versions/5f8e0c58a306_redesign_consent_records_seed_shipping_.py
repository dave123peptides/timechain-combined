"""redesign consent_records; seed shipping system_setting

consent_records had 0 rows and a generic, never-wired-up shape
(consent_type/granted/version). Redesigning it to the checkout-specific
shape actually used by app.services.storefront.create_order: one row
per order, capturing all three checkout consents (age/RUO/terms)
together, with the document versions the backend stamped at the time.

Also seeds system_settings with the launch flat shipping rate — backend
reads this rather than any code hard-coding the dollar amount.

Revision ID: 5f8e0c58a306
Revises: 21f701e15635
Create Date: 2026-08-13 09:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f8e0c58a306'
down_revision: str | None = '21f701e15635'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column('consent_records', 'subject_email')
    op.drop_column('consent_records', 'consent_type')
    op.drop_column('consent_records', 'granted')
    op.drop_column('consent_records', 'version')
    op.drop_column('consent_records', 'ip_address')
    op.drop_column('consent_records', 'user_agent')

    op.alter_column('consent_records', 'order_id', existing_type=sa.UUID(), nullable=False)
    op.create_unique_constraint(op.f('uq_consent_records_order_id'), 'consent_records', ['order_id'])

    op.add_column('consent_records', sa.Column('age_acknowledged_at', sa.DateTime(timezone=True), nullable=False))
    op.add_column('consent_records', sa.Column('ruo_acknowledged_at', sa.DateTime(timezone=True), nullable=False))
    op.add_column('consent_records', sa.Column('ruo_terms_version', sa.String(length=20), nullable=False))
    op.add_column('consent_records', sa.Column('terms_version', sa.String(length=20), nullable=False))
    op.add_column('consent_records', sa.Column('privacy_version', sa.String(length=20), nullable=False))

    # orders.id is ON DELETE CASCADE now (was SET NULL against a
    # nullable column) — drop and recreate the FK to match.
    op.drop_constraint(
        op.f('fk_consent_records_order_id_orders'), 'consent_records', type_='foreignkey'
    )
    op.create_foreign_key(
        op.f('fk_consent_records_order_id_orders'),
        'consent_records', 'orders', ['order_id'], ['id'], ondelete='CASCADE',
    )

    op.execute(
        """
        INSERT INTO system_settings (key, value, description)
        VALUES (
            'shipping.us_flat_rate_cents',
            '{"amount_cents": 4000}'::jsonb,
            'Launch flat shipping rate for US orders, in cents. Backend-authoritative — never hard-code this in the frontend.'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE key = 'shipping.us_flat_rate_cents'")

    op.drop_constraint(op.f('fk_consent_records_order_id_orders'), 'consent_records', type_='foreignkey')
    op.create_foreign_key(
        op.f('fk_consent_records_order_id_orders'),
        'consent_records', 'orders', ['order_id'], ['id'], ondelete='SET NULL',
    )

    op.drop_column('consent_records', 'privacy_version')
    op.drop_column('consent_records', 'terms_version')
    op.drop_column('consent_records', 'ruo_terms_version')
    op.drop_column('consent_records', 'ruo_acknowledged_at')
    op.drop_column('consent_records', 'age_acknowledged_at')

    op.drop_constraint(op.f('uq_consent_records_order_id'), 'consent_records', type_='unique')
    op.alter_column('consent_records', 'order_id', existing_type=sa.UUID(), nullable=True)

    op.add_column('consent_records', sa.Column('user_agent', sa.Text(), nullable=True))
    op.add_column('consent_records', sa.Column('ip_address', sa.String(length=45), nullable=True))
    op.add_column('consent_records', sa.Column('version', sa.String(length=50), nullable=False))
    op.add_column('consent_records', sa.Column('granted', sa.Boolean(), nullable=False))
    op.add_column('consent_records', sa.Column('consent_type', sa.String(length=50), nullable=False))
    op.add_column('consent_records', sa.Column('subject_email', sa.String(length=320), nullable=True))
