"""Manual entrypoint: python -m app.catalog_import.run <xlsx-path>

Imports the TimeChain wholesale/retail price sheet into products/
product_variants and auto-links EXACT matches against supplier_products.
Never makes anything customer-visible or sellable, never sends a
TimeChain name to a supplier, and never auto-links anything but an EXACT
match — see app/catalog_import/sync.py.
"""

import logging
import sys
from pathlib import Path

from app.catalog_import.price_sheet import PriceSheetFormatError
from app.catalog_import.sync import run_catalog_import
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO)


def _default_report_dir() -> str:
    """In docker-compose the repo's data/ is mounted at /data (see
    docker-compose.yml); running natively (no container) fall back to the
    data/catalog_import directory in the repo itself."""
    docker_mount = Path("/data/catalog_import")
    if docker_mount.exists():
        return str(docker_mount)
    repo_root = Path(__file__).resolve().parents[4]
    return str(repo_root / "data" / "catalog_import")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m app.catalog_import.run <xlsx-path>", file=sys.stderr)
        return 2

    xlsx_path = sys.argv[1]
    session = SessionLocal()
    try:
        try:
            summary = run_catalog_import(session, xlsx_path, report_dir=_default_report_dir())
        except PriceSheetFormatError as exc:
            session.rollback()
            print(f"Price sheet format error: {exc}", file=sys.stderr)
            return 2
        session.commit()
    finally:
        session.close()

    print("Catalog import summary:")
    print(f"  rows_retrieved:    {summary.rows_retrieved}")
    print(f"  products_created:  {summary.products_created}")
    print(f"  products_existing: {summary.products_existing}")
    print(f"  variants_created:  {summary.variants_created}")
    print(f"  variants_updated:  {summary.variants_updated}")
    print(f"  mappings_exact:    {summary.mappings_exact}")
    print(f"  pending_likely:    {summary.pending_likely}")
    print(f"  pending_ambiguous: {summary.pending_ambiguous}")
    print(f"  pending_no_match:  {summary.pending_no_match}")
    print(f"  errors:            {summary.errors}")
    print(f"  report_written_to: {summary.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
