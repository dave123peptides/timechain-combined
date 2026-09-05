"""Read-only comparison of the real AllianceTek Production catalog
against the catalog currently known locally (the `supplier_products`
table, populated by the Sandbox-pointed sync in
worker/supplier_sync/sync.py).

This module never writes to `supplier_products`, `products`,
`product_variants`, or `supplier_product_mappings` — it only reads and
reports. Nothing here can change what's sellable on the storefront;
that's a deliberate, separate, human-reviewed step, same posture as
worker/supplier_sync/sync.py's own db.py docstring.

Sandbox and Production productIds are NOT assumed to line up — matching
is done on `supplier_sku`, the one identifier expected to stay stable
across AllianceTek environments. A `supplier_product_id` (or name)
mismatch on an otherwise-matching SKU is reported as "changed", never
silently ignored or treated as unrelated.
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

from worker.alliancetek.client import AllianceTekClient
from worker.config import Settings, get_settings
from worker.supplier_sync.db import supplier_products_table
from worker.supplier_sync.mapping import SupplierProductFieldError, map_supplier_product
from worker.supplier_sync.sync import fetch_all_supplier_products

logger = logging.getLogger("timechain.worker.supplier_sync.production_report")


class ProductionReportConfigError(RuntimeError):
    """Raised when supplier_api_production_* is not fully configured."""


@dataclass(frozen=True)
class CatalogEntry:
    supplier_product_id: int
    supplier_sku: str
    supplier_name: str


@dataclass(frozen=True)
class ChangedEntry:
    supplier_sku: str
    baseline: CatalogEntry
    production: CatalogEntry
    differences: tuple[str, ...]


@dataclass(frozen=True)
class ComparisonReport:
    same: list[CatalogEntry] = field(default_factory=list)
    changed: list[ChangedEntry] = field(default_factory=list)
    # In the local baseline (Sandbox-synced) but absent from Production.
    missing: list[CatalogEntry] = field(default_factory=list)
    # In Production but absent from the local baseline.
    new: list[CatalogEntry] = field(default_factory=list)
    baseline_errors: int = 0
    production_errors: int = 0


def compare_catalogs(baseline: list[CatalogEntry], production: list[CatalogEntry]) -> ComparisonReport:
    """Pure comparison — no I/O. Matches by supplier_sku; reports a
    supplier_product_id or supplier_name difference on a matched SKU as
    "changed" rather than treating productId as the join key."""
    baseline_by_sku = {entry.supplier_sku: entry for entry in baseline}
    production_by_sku = {entry.supplier_sku: entry for entry in production}

    report = ComparisonReport()

    for sku, baseline_entry in baseline_by_sku.items():
        production_entry = production_by_sku.get(sku)
        if production_entry is None:
            report.missing.append(baseline_entry)
            continue

        differences = []
        if baseline_entry.supplier_product_id != production_entry.supplier_product_id:
            differences.append("productId")
        if baseline_entry.supplier_name != production_entry.supplier_name:
            differences.append("name")

        if differences:
            report.changed.append(
                ChangedEntry(
                    supplier_sku=sku,
                    baseline=baseline_entry,
                    production=production_entry,
                    differences=tuple(differences),
                )
            )
        else:
            report.same.append(production_entry)

    for sku, production_entry in production_by_sku.items():
        if sku not in baseline_by_sku:
            report.new.append(production_entry)

    return report


def load_baseline_catalog(conn: Connection) -> list[CatalogEntry]:
    rows = conn.execute(
        sa.select(
            supplier_products_table.c.supplier_product_id,
            supplier_products_table.c.supplier_sku,
            supplier_products_table.c.supplier_name,
        )
    ).all()
    return [CatalogEntry(supplier_product_id=r[0], supplier_sku=r[1], supplier_name=r[2]) for r in rows]


def fetch_production_catalog(client: AllianceTekClient) -> tuple[list[CatalogEntry], int]:
    """Returns (entries, error_count). A record this environment's
    mapper can't parse is counted as an error and skipped — never
    guessed — same posture as worker/supplier_sync/sync.py's run_sync."""
    raw_products, reported_total, pages_fetched = fetch_all_supplier_products(client)
    if len(raw_products) != reported_total:
        logger.warning(
            "production_report: fetched %s products across %s pages, but the API reported total=%s — "
            "report may be based on an incomplete Production catalog",
            len(raw_products),
            pages_fetched,
            reported_total,
        )

    entries: list[CatalogEntry] = []
    error_count = 0
    for raw in raw_products:
        try:
            mapped = map_supplier_product(raw)
        except SupplierProductFieldError as exc:
            error_count += 1
            logger.warning("production_report: skipping unmappable Production record: %s", exc)
            continue
        entries.append(
            CatalogEntry(
                supplier_product_id=mapped["supplier_product_id"],
                supplier_sku=mapped["supplier_sku"],
                supplier_name=mapped["supplier_name"],
            )
        )
    return entries, error_count


def run_production_report(*, settings: Optional[Settings] = None, engine: Optional[Engine] = None) -> ComparisonReport:
    """Orchestrates the read-only Production-vs-baseline comparison.
    Writes nothing to any table; only issues GET-shaped calls against the
    real AllianceTek Production products endpoint."""
    settings = settings or get_settings()
    if not (
        settings.supplier_api_production_products_url
        and settings.supplier_api_production_email
        and settings.supplier_api_production_token
    ):
        raise ProductionReportConfigError(
            "SUPPLIER_API_PRODUCTION_PRODUCTS_URL / SUPPLIER_API_PRODUCTION_EMAIL / "
            "SUPPLIER_API_PRODUCTION_TOKEN must all be set to run the production catalog report."
        )

    client = AllianceTekClient(
        products_url=settings.supplier_api_production_products_url,
        email=settings.supplier_api_production_email,
        api_token=settings.supplier_api_production_token,
        environment="production",
        timeout_seconds=settings.supplier_api_timeout_seconds,
        max_retries=settings.supplier_api_max_retries,
    )
    try:
        production_entries, production_errors = fetch_production_catalog(client)
    finally:
        client.close()

    owns_engine = engine is None
    engine = engine or create_engine(settings.database_url)
    try:
        with engine.connect() as conn:
            baseline_entries = load_baseline_catalog(conn)
    finally:
        if owns_engine:
            engine.dispose()

    report = compare_catalogs(baseline_entries, production_entries)
    return ComparisonReport(
        same=report.same,
        changed=report.changed,
        missing=report.missing,
        new=report.new,
        baseline_errors=0,
        production_errors=production_errors,
    )


def _print_report(report: ComparisonReport) -> None:
    print("Production supplier catalog report (matched on supplier_sku):")
    print(f"  same:    {len(report.same)}")
    print(f"  changed: {len(report.changed)}")
    print(f"  missing: {len(report.missing)}  (in local/Sandbox baseline, not found in Production)")
    print(f"  new:     {len(report.new)}  (in Production, not in local/Sandbox baseline)")
    if report.production_errors:
        print(f"  production_errors: {report.production_errors}  (unmappable records, skipped — see logs)")

    if report.changed:
        print("\nChanged (SKU matches, but productId and/or name differs):")
        for entry in report.changed:
            print(
                f"  sku={entry.supplier_sku!r} differs on {list(entry.differences)}: "
                f"baseline productId={entry.baseline.supplier_product_id!r} name={entry.baseline.supplier_name!r} "
                f"-> production productId={entry.production.supplier_product_id!r} name={entry.production.supplier_name!r}"
            )

    if report.missing:
        print("\nMissing from Production (no equivalent SKU found):")
        for entry in report.missing:
            print(f"  sku={entry.supplier_sku!r} name={entry.supplier_name!r} (baseline productId={entry.supplier_product_id!r})")

    if report.new:
        print("\nNew in Production (no equivalent SKU in local baseline):")
        for entry in report.new:
            print(f"  sku={entry.supplier_sku!r} name={entry.supplier_name!r} (production productId={entry.supplier_product_id!r})")


def main() -> int:
    """Manual entrypoint: python -m worker.supplier_sync.production_report

    Read-only — never writes to supplier_products, product mappings, or
    sellability. Run this to see how the real Production catalog lines
    up against what's currently known (Sandbox-synced) before doing
    anything else with it; nothing here enables checkout or touches
    mapping state.
    """
    logging.basicConfig(level=logging.INFO)
    try:
        report = run_production_report()
    except ProductionReportConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
