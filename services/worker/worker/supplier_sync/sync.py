from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from worker.alliancetek.client import AllianceTekClient, SupplierApiError
from worker.config import get_settings
from worker.supplier_sync.db import upsert_supplier_products
from worker.supplier_sync.mapping import SupplierProductFieldError, map_supplier_product
from worker.supplier_sync.reconciliation import get_mapped_supplier_product_ids, reconcile_mapping_drift

logger = logging.getLogger("timechain.worker.supplier_sync")

# If more than this fraction of currently-MAPPED supplier products would be
# marked "disappeared" in one run, abort instead of downgrading them —
# almost certainly a fetch/config problem (wrong environment, truncated
# response that still happened to pass the count check, etc.), not real
# attrition. A single genuinely-discontinued product should never come
# close to this; losing most of the mapped catalog in one sync shouldn't
# be possible without a loud failure first.
_MAX_DISAPPEARED_FRACTION = 0.5


class SupplierSyncValidationError(RuntimeError):
    """Raised when the number of products actually fetched doesn't match
    the supplier's reported total, or when an implausible fraction of the
    currently-mapped catalog would be marked disappeared — better to stop
    the sync than upsert an incomplete/wrong catalog or mass-revoke
    mappings that are probably still fine."""


@dataclass(frozen=True)
class SyncResult:
    retrieved: int
    inserted: int
    updated: int
    unchanged: int
    errors: int
    mappings_changed: int
    mappings_missing: int
    variants_deactivated: int
    reported_total: int
    pages_fetched: int


def fetch_all_supplier_products(client: AllianceTekClient) -> tuple[list[dict[str, Any]], int, int]:
    """Fetches every page of the supplier product catalog.

    Neither the page count nor the product count is hard-coded — both
    come from the API's own `result.pages` / `result.total`, read from
    page 1 and used as the loop bound for the remaining pages.
    """
    first_page = client.list_products(1)
    total_pages = first_page.pages
    reported_total = first_page.total

    if total_pages < 1:
        raise SupplierApiError(f"Supplier API reported {total_pages} pages on page 1.")

    all_products: list[dict[str, Any]] = list(first_page.products)

    for page_number in range(2, total_pages + 1):
        page = client.list_products(page_number)
        if page.pages != total_pages or page.total != reported_total:
            logger.warning(
                "supplier_sync: page %s reported pages=%s/total=%s, differs from page 1's "
                "pages=%s/total=%s — catalog may have changed mid-sync",
                page_number,
                page.pages,
                page.total,
                total_pages,
                reported_total,
            )
        all_products.extend(page.products)

    return all_products, reported_total, total_pages


def run_sync(*, engine: Optional[Engine] = None) -> SyncResult:
    """Fetches the full supplier product catalog for every configured
    supplier key (settings.supplier_keys, e.g. "umsrx,nxgen") and upserts
    it into `supplier_products`, stamped per supplier. Raises
    `SupplierSyncValidationError` if any supplier's fetched count doesn't
    match the API's reported total — nothing is written in that case.
    """
    settings = get_settings()
    supplier_keys = [key.strip() for key in settings.supplier_keys.split(",") if key.strip()] or ["umsrx"]

    owns_engine = engine is None
    engine = engine or create_engine(settings.database_url)

    totals = SyncResult(
        retrieved=0, inserted=0, updated=0, unchanged=0, errors=0,
        mappings_changed=0, mappings_missing=0, variants_deactivated=0,
        reported_total=0, pages_fetched=0,
    )
    try:
        for supplier_key in supplier_keys:
            result = _run_sync_for_supplier(settings, engine, supplier_key)
            totals = SyncResult(
                retrieved=totals.retrieved + result.retrieved,
                inserted=totals.inserted + result.inserted,
                updated=totals.updated + result.updated,
                unchanged=totals.unchanged + result.unchanged,
                errors=totals.errors + result.errors,
                mappings_changed=totals.mappings_changed + result.mappings_changed,
                mappings_missing=totals.mappings_missing + result.mappings_missing,
                variants_deactivated=totals.variants_deactivated + result.variants_deactivated,
                reported_total=totals.reported_total + result.reported_total,
                pages_fetched=totals.pages_fetched + result.pages_fetched,
            )
    finally:
        if owns_engine:
            engine.dispose()
    return totals


def _run_sync_for_supplier(settings: Any, engine: Engine, supplier_key: str) -> SyncResult:
    client = AllianceTekClient.from_settings_for_supplier(settings, supplier_key)
    try:
        raw_products, reported_total, pages_fetched = fetch_all_supplier_products(client)
    finally:
        client.close()

    if len(raw_products) != reported_total:
        raise SupplierSyncValidationError(
            f"[{supplier_key}] Fetched {len(raw_products)} supplier products across {pages_fetched} pages, "
            f"but the API reported total={reported_total}. Aborting without writing to the database."
        )

    # A single malformed record shouldn't sink the whole sync — map what we
    # can, count the rest as errors, and still upsert the good rows.
    rows: list[dict[str, Any]] = []
    error_count = 0
    for product in raw_products:
        try:
            rows.append(map_supplier_product(product, supplier_key=supplier_key))
        except SupplierProductFieldError as exc:
            error_count += 1
            logger.warning("supplier_sync[%s]: skipping unmappable product record: %s", supplier_key, exc)

    with engine.begin() as conn:
        upsert_result = upsert_supplier_products(conn, rows, now=datetime.now(timezone.utc))

        # A currently-MAPPED supplier product of THIS supplier missing from
        # this run's rows has disappeared from the feed — trustworthy only
        # because the count check above already confirmed this fetch is
        # complete, not a partial/glitched one. Scoped to the supplier: the
        # other supplier's catalog says nothing about this one's products.
        fetched_ids = {row["supplier_product_id"] for row in rows}
        mapped_ids = get_mapped_supplier_product_ids(conn, supplier_key)
        disappeared_ids = list(mapped_ids - fetched_ids)

        if mapped_ids and len(disappeared_ids) / len(mapped_ids) > _MAX_DISAPPEARED_FRACTION:
            raise SupplierSyncValidationError(
                f"[{supplier_key}] {len(disappeared_ids)}/{len(mapped_ids)} currently-MAPPED supplier products "
                "are missing from this sync's fetch. Aborting without changing any mapping — "
                "this looks like a fetch/config problem, not real attrition."
            )

        reconciliation_result = reconcile_mapping_drift(
            conn,
            changed_supplier_product_ids=upsert_result.changed_identity_ids,
            disappeared_supplier_product_ids=disappeared_ids,
            supplier_key=supplier_key,
        )

    logger.info(
        "supplier_sync[%s]: retrieved=%s inserted=%s updated=%s unchanged=%s errors=%s "
        "mappings_changed=%s mappings_missing=%s variants_deactivated=%s (across %s pages)",
        supplier_key,
        len(raw_products),
        upsert_result.inserted,
        upsert_result.updated,
        upsert_result.unchanged,
        error_count,
        reconciliation_result.mappings_marked_changed,
        reconciliation_result.mappings_marked_missing,
        reconciliation_result.variants_deactivated,
        pages_fetched,
    )
    return SyncResult(
        retrieved=len(raw_products),
        inserted=upsert_result.inserted,
        updated=upsert_result.updated,
        unchanged=upsert_result.unchanged,
        errors=error_count,
        mappings_changed=reconciliation_result.mappings_marked_changed,
        mappings_missing=reconciliation_result.mappings_marked_missing,
        variants_deactivated=reconciliation_result.variants_deactivated,
        reported_total=reported_total,
        pages_fetched=pages_fetched,
    )
