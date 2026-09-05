"""recategorize products into the launch merchandising taxonomy

Product.category was stamped once, at product creation, from whichever
price-sheet tab first produced the row — so it describes the supplier's
spreadsheet layout, not what TimeChain sells. After David's 2026-08-22
lyophilized-only decision those labels became actively wrong: of the 32
sellable products, 21 were labeled 'RUO Pens' and 5 'RUO Vials' while
every sellable variant is form='lyophilized' (ProductVariant's
_validate_is_sellable rejects pen / vial / preconstituted / rx_vial
outright). Category drives the homepage nav, the /shop filter pills, the
footer links and the PDP tag, so shipping 'RUO Pens (21)' on a storefront
that sells zero pens would put a factual misstatement in the most
prominent navigation on the site.

This applies the six-category merchandising taxonomy David approved with
the curated ladder (2026-08-22/23):

  before (32 sellable)      after (32 sellable)
    RUO Pens         21       Healing & Repair Blends      8
    RUO Lyophilized   6       Longevity & Cognitive        8
    RUO Vials         5       Growth Hormone & Recovery    6
                              GLP-1 & Metabolic            5
                              Sexual Health & Hormonal     4
                              Supplies                     1

35 slugs are mapped, not 32. ghrp-6, kisspeptin and
tesamorelin-ipamorelin have no verified lyophilized supplier mapping yet
and so are not currently sellable; mapping them here means they arrive
correctly categorized whenever admin approval makes them live, instead of
surfacing under a stale import label.

The 35 pairs below are a deliberately FROZEN snapshot of
app.constants.product_categories.PRODUCT_CATEGORY_BY_SLUG. This migration
must not import that module: an already-applied migration whose behaviour
changes when a constant is edited is not reproducible. The constant is the
living source of truth (app.scripts.sync_lyo_catalog reads it, so a
catalog re-import re-normalizes to the same taxonomy); this literal is
history. To change the taxonomy, write a new revision.

downgrade() restores from a snapshot table rather than recomputing. The
old labels were assigned per-product by whichever supplier sheet won the
race at import time and are not derivable from the slug, so a snapshot is
the only faithful way to reverse this. The table is underscore-prefixed
and revision-suffixed so it cannot be mistaken for a domain table, and is
retained after upgrade because it *is* the downgrade data. On a fresh
database it is created empty and downgrade is a correct no-op.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-30 00:10:00.000000

"""
from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: str | None = 'c3d4e5f6a7b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKUP_TABLE = '_products_category_backup_d4e5f6a7b8c9'


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_BACKUP_TABLE} AS
        SELECT id, category FROM products
        """
    )
    op.execute(
        """
        UPDATE products AS p
        SET category = m.category
        FROM (VALUES
            ('glp-1s', 'GLP-1 & Metabolic'),
            ('glp-2t', 'GLP-1 & Metabolic'),
            ('glp-3r', 'GLP-1 & Metabolic'),
            ('cagrilinitide', 'GLP-1 & Metabolic'),
            ('aod-9604', 'GLP-1 & Metabolic'),
            ('tesamorelin', 'Growth Hormone & Recovery'),
            ('sermorelin', 'Growth Hormone & Recovery'),
            ('ipamorelin', 'Growth Hormone & Recovery'),
            ('tesamorelin-ipamorelin', 'Growth Hormone & Recovery'),
            ('cjc-no-dac-ipamorelin', 'Growth Hormone & Recovery'),
            ('ghrp-2', 'Growth Hormone & Recovery'),
            ('ghrp-6', 'Growth Hormone & Recovery'),
            ('mots-c', 'Growth Hormone & Recovery'),
            ('bpc-157', 'Healing & Repair Blends'),
            ('tb-500', 'Healing & Repair Blends'),
            ('bpc-157-tb-500-wolverine', 'Healing & Repair Blends'),
            ('glow-bpc-157-tb-500-ghk', 'Healing & Repair Blends'),
            ('klow-kpv-bpc-157-tb-500-ghk', 'Healing & Repair Blends'),
            ('kpv', 'Healing & Repair Blends'),
            ('ghk-cu', 'Healing & Repair Blends'),
            ('ghk-cu-kpv', 'Healing & Repair Blends'),
            ('nad', 'Longevity & Cognitive'),
            ('epithalon', 'Longevity & Cognitive'),
            ('ss-31', 'Longevity & Cognitive'),
            ('ta-1', 'Longevity & Cognitive'),
            ('dsip', 'Longevity & Cognitive'),
            ('selank', 'Longevity & Cognitive'),
            ('semax', 'Longevity & Cognitive'),
            ('kisspeptin', 'Longevity & Cognitive'),
            ('igf1-lr3', 'Longevity & Cognitive'),
            ('pt-141', 'Sexual Health & Hormonal'),
            ('mt-1', 'Sexual Health & Hormonal'),
            ('mt-2', 'Sexual Health & Hormonal'),
            ('hcg-6000-units', 'Sexual Health & Hormonal'),
            ('bac-water', 'Supplies')
        ) AS m(slug, category)
        WHERE p.slug = m.slug
          AND p.category IS DISTINCT FROM m.category
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE products AS p
        SET category = b.category
        FROM {_BACKUP_TABLE} AS b
        WHERE p.id = b.id
          AND p.category IS DISTINCT FROM b.category
        """
    )
    op.execute(f'DROP TABLE IF EXISTS {_BACKUP_TABLE}')
