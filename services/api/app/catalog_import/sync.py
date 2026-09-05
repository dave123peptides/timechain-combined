from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog_import.matching import classify_match
from app.catalog_import.price_sheet import PriceSheetRow, parse_price_sheet
from app.constants.forms import FORM_LABEL as _FORM_LABEL
from app.models.catalog import Product, ProductVariant, SupplierProduct, SupplierProductMapping

logger = logging.getLogger("timechain.api.catalog_import")

_MONTH_SUFFIX = re.compile(r"\s+month\s*\d+\s*$", re.IGNORECASE)
_SLUG_NOISE = re.compile(r"[^a-z0-9]+")


class CatalogImportRowError(RuntimeError):
    """Raised for a single unusable price-sheet row (e.g. missing a
    required retail price) — the row is skipped and counted as an error
    rather than aborting the whole import, same pattern as
    worker/supplier_sync/sync.py uses for unmappable supplier records."""


def _slugify(text: str) -> str:
    slug = _SLUG_NOISE.sub("-", text.strip().lower()).strip("-")
    return slug or "product"


def _base_product_name(product_name: str) -> str:
    """Strips a trailing "Month N" dose-tier suffix so e.g. "Semaglutide
    Month 1".."Month 5" group under one Product ("Semaglutide"), each its
    own ProductVariant. Doesn't reconcile other naming differences across
    sheets (e.g. "Reta" vs "Retatrutide") — see the plan's documented
    limitation; those simply become separate Product rows."""
    stripped = _MONTH_SUFFIX.sub("", product_name).strip()
    return stripped or product_name


def _variant_sku(base_slug: str, form: str, size_key: Optional[str]) -> str:
    size_token = (size_key or "NA").upper().replace("/", "-")
    form_token = form.upper().replace("_", "-")
    return f"TC-{base_slug.upper()}-{form_token}-{size_token}"[:100]


def _variant_name(product_name: str, form: str, size_key: Optional[str]) -> str:
    label = _FORM_LABEL.get(form, form.title())
    if size_key:
        # size_key is usually a bare mg number/combo ("10", "10/10") that
        # needs "mg" appended for display, but some rows (e.g. BAC Water's
        # "10mL") already carry their own unit — appending "mg" to those
        # would read as "10mLmg". Only append when size_key is purely
        # numeric/slash-separated.
        size_display = f"{size_key}mg" if re.fullmatch(r"[\d/]+", size_key) else size_key
        return f"{product_name} {size_display} ({label})"
    return f"{product_name} ({label})"


@dataclass
class SyncSummary:
    rows_retrieved: int = 0
    products_created: int = 0
    products_existing: int = 0
    variants_created: int = 0
    variants_updated: int = 0
    mappings_exact: int = 0
    pending_likely: int = 0
    pending_ambiguous: int = 0
    pending_no_match: int = 0
    errors: int = 0
    report_path: Optional[str] = None


def _get_or_create_product(
    session: Session, *, slug: str, name: str, category: Optional[str], summary: SyncSummary
) -> Product:
    product = session.execute(select(Product).where(Product.slug == slug)).scalar_one_or_none()
    if product is not None:
        summary.products_existing += 1
        return product
    # Never customer-visible on creation — a human opts a product in later.
    product = Product(slug=slug, name=name, category=category, images=[], is_active=False)
    session.add(product)
    session.flush()
    summary.products_created += 1
    return product


def _get_or_create_variant(
    session: Session,
    *,
    product: Product,
    sku: str,
    name: str,
    retail_cents: int,
    wholesale_cents: Optional[int],
    size_key: Optional[str],
    form: str,
    summary: SyncSummary,
) -> ProductVariant:
    variant = session.execute(select(ProductVariant).where(ProductVariant.sku == sku)).scalar_one_or_none()
    if variant is not None:
        # Re-importing refreshes name/pricing (that's the point of running
        # the price sheet through again) but never touches is_sellable —
        # a human's decision to make something sellable must survive a
        # re-import, exactly like first_seen_at survives a supplier resync.
        # size_key/form are likewise safe to refresh: they're derived
        # purely from this row's own sheet data, not admin-editable state.
        variant.name = name
        variant.retail_price_cents = retail_cents
        variant.wholesale_cost_cents = wholesale_cents
        variant.size_key = size_key
        variant.form = form
        summary.variants_updated += 1
        return variant
    variant = ProductVariant(
        product_id=product.id,
        sku=sku,
        name=name,
        retail_price_cents=retail_cents,
        wholesale_cost_cents=wholesale_cents,
        size_key=size_key,
        form=form,
        is_sellable=False,
    )
    session.add(variant)
    session.flush()
    summary.variants_created += 1
    return variant


def _upsert_mapping(
    session: Session, *, product_variant_id, supplier_product: SupplierProduct
) -> SupplierProductMapping:
    mapping = session.execute(
        select(SupplierProductMapping).where(
            SupplierProductMapping.product_variant_id == product_variant_id,
            SupplierProductMapping.supplier_product_id == supplier_product.supplier_product_id,
        )
    ).scalar_one_or_none()
    if mapping is not None:
        if mapping.mapping_status != "MAPPED":
            # Re-running the price-sheet import must never silently
            # re-approve a mapping that sync reconciliation downgraded —
            # that's an admin's call (app.services.mapping_status.
            # approve_mapping), not something a routine re-import does by
            # coincidentally reconfirming the same EXACT classification.
            # Leave the row completely untouched, snapshot included.
            return mapping
        # Snapshot refreshed to the current supplier_products state — see
        # SupplierProductMapping's docstring on why this is a snapshot,
        # not a live join, once an order actually reads it.
        mapping.supplier_sku = supplier_product.supplier_sku
        mapping.supplier_name = supplier_product.supplier_name
        mapping.supplier_key = supplier_product.supplier_key
        mapping.is_active = True
        return mapping
    mapping = SupplierProductMapping(
        product_variant_id=product_variant_id,
        supplier_product_id=supplier_product.supplier_product_id,
        supplier_key=supplier_product.supplier_key,
        supplier_sku=supplier_product.supplier_sku,
        supplier_name=supplier_product.supplier_name,
        priority=0,
        is_active=True,
        mapping_status="MAPPED",
        match_confidence="EXACT",
    )
    session.add(mapping)
    # Flush so a later row in the same run that resolves to the same
    # (variant, supplier) pair sees this pending INSERT in its SELECT —
    # without it (autoflush=False) the second _upsert_mapping double-inserts
    # and trips uq_supplier_product_mappings_variant_supplier. Same pattern
    # as the flush in _get_or_create_product/_get_or_create_variant.
    session.flush()
    return mapping


def _process_row(
    session: Session, row: PriceSheetRow, supplier_products: list[SupplierProduct], summary: SyncSummary
) -> Optional[dict]:
    """Returns a pending-review record for non-EXACT rows, or None if the
    row was auto-mapped (EXACT)."""
    if row.retail_cents is None:
        raise CatalogImportRowError(
            f"Row {row.product_name!r} (sheet {row.sheet!r}) has no retail price — refusing to "
            f"guess a price for a customer-facing field."
        )

    base_name = _base_product_name(row.product_name)
    slug = _slugify(base_name)
    product = _get_or_create_product(session, slug=slug, name=base_name, category=row.category, summary=summary)

    sku = _variant_sku(slug, row.form, row.size_key)
    variant_name = _variant_name(row.product_name, row.form, row.size_key)
    variant = _get_or_create_variant(
        session,
        product=product,
        sku=sku,
        name=variant_name,
        retail_cents=row.retail_cents,
        wholesale_cents=row.wholesale_cents,
        size_key=row.size_key,
        form=row.form,
        summary=summary,
    )

    result = classify_match(
        product_name=row.product_name, size_key=row.size_key, form=row.form, supplier_products=supplier_products
    )

    if result.status == "EXACT":
        assert result.best is not None
        supplier_product = next(
            sp for sp in supplier_products if sp.supplier_product_id == result.best.supplier_product_id
        )
        _upsert_mapping(session, product_variant_id=variant.id, supplier_product=supplier_product)
        summary.mappings_exact += 1
        return None

    if result.status == "LIKELY":
        summary.pending_likely += 1
    elif result.status == "AMBIGUOUS":
        summary.pending_ambiguous += 1
    else:
        summary.pending_no_match += 1

    return {
        "sheet": row.sheet,
        "product_name": row.product_name,
        "size_key": row.size_key,
        "form": row.form,
        "variant_sku": sku,
        "status": result.status,
        "candidates": [
            {
                "supplier_product_id": candidate.supplier_product_id,
                "supplier_sku": candidate.supplier_sku,
                "supplier_name": candidate.supplier_name,
                "score": candidate.score,
                "name_ratio": candidate.name_ratio,
                "size_match": candidate.size_match,
            }
            for candidate in result.candidates
        ],
    }


def run_catalog_import(session: Session, xlsx_path: str, *, report_dir: str = "/data/catalog_import") -> SyncSummary:
    """Parses the price sheet, get-or-creates Product/ProductVariant rows
    (never sellable/active by default), auto-links only EXACT matches
    against the current supplier_products, and writes every non-EXACT row
    to a JSON report for manual review. Never touches an existing
    variant's is_sellable, and never creates a mapping for anything but an
    EXACT match.
    """
    rows = parse_price_sheet(xlsx_path)
    summary = SyncSummary(rows_retrieved=len(rows))
    supplier_products = list(session.execute(select(SupplierProduct)).scalars())

    pending: list[dict] = []
    for row in rows:
        try:
            pending_entry = _process_row(session, row, supplier_products, summary)
        except CatalogImportRowError as exc:
            summary.errors += 1
            logger.warning("catalog_import: skipping row: %s", exc)
            continue
        if pending_entry is not None:
            pending.append(pending_entry)

    report_dir_path = Path(report_dir)
    report_dir_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = report_dir_path / f"report_{timestamp}.json"
    report_path.write_text(json.dumps({"generated_at": timestamp, "pending": pending}, indent=2))
    summary.report_path = str(report_path)

    return summary
