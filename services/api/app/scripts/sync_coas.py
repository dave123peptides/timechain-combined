"""Manual entrypoint: python -m app.scripts.sync_coas [--manifest PATH] [--publish-client NAME ...]

Loads services/api/data/coa/coa_manifest.csv (built from the certificate
PDFs by app.scripts.build_coa_manifest) into `product_coas`, keyed by the
lab's verification code. Run it after the manifest changes — locally by
hand; in production it runs automatically inside every Vercel build of
the API (scripts/vercel-build.sh), right after migrations.

Per manifest row:
- Product looked up by slug. An unknown slug is skipped and reported,
  never invented: a certificate for a compound that isn't in the catalog
  has nowhere honest to go.
- Existing row (same verify_code): every fact re-synced from the
  manifest EXCEPT is_published, which is left exactly as it is. A person
  who hid a certificate must not have it silently re-published by the
  next sync — same "nothing automated moves it back" stance as
  SupplierProductMapping.mapping_status.
- New row: inserted, published only when the certificate's client (the
  company the lab issued it to) is in --publish-client. Default is our
  supplier, NxGen Bio Med. A handful of older certificates in the folder
  were issued to a different company (Valor Peptides); they load
  unpublished so David can decide whether paperwork made out to another
  vendor belongs on our product pages. Publish them by flipping
  is_published in the database, or re-run with --publish-client for both
  names and --reset-published.

Never deletes. A database row whose verify_code has left the manifest is
reported as an orphan, not removed — a certificate we once published
should be withdrawn on purpose, not by omission.

Idempotent — re-running with an unchanged manifest changes nothing.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.catalog import Product, ProductCoa
from app.scripts.build_coa_manifest import MANIFEST_COLUMNS, default_manifest_path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_PUBLISH_CLIENTS = ("NxGen Bio Med",)


@dataclass(frozen=True)
class SyncReport:
    inserted: int
    updated: int
    unchanged: int
    skipped_unknown_slug: list[str]
    inserted_unpublished: int
    orphaned_codes: list[str]


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in MANIFEST_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: manifest is missing columns {missing}")
        return list(reader)


def sync_coas(
    session: Session,
    rows: list[dict[str, str]],
    *,
    publish_clients: tuple[str, ...] = DEFAULT_PUBLISH_CLIENTS,
    reset_published: bool = False,
) -> SyncReport:
    """Apply the manifest to the session. Commits nothing — the caller
    decides (main() commits; tests roll back)."""
    products_by_slug = {p.slug: p for p in session.execute(select(Product)).scalars()}
    existing_by_code = {c.verify_code: c for c in session.execute(select(ProductCoa)).scalars()}

    inserted = updated = unchanged = inserted_unpublished = 0
    skipped: list[str] = []
    manifest_codes: set[str] = set()

    for row in rows:
        code = row["verify_code"].strip()
        manifest_codes.add(code)
        product = products_by_slug.get(row["slug"].strip())
        if product is None:
            skipped.append(f"{row['slug']} ({code})")
            continue

        publish = row["client"].strip() in publish_clients
        facts = {
            "product_id": product.id,
            "strength": row["strength"].strip() or None,
            "lot": row["lot"].strip(),
            "issued_on": date.fromisoformat(row["issued_on"].strip()),
            "lab": row["lab"].strip(),
            "client": row["client"].strip(),
            "tests": [t for t in row["tests"].split("|") if t],
            "pdf_url": row["pdf_url"].strip(),
            "verify_url": row["verify_url"].strip() or None,
            "source_file": row["source_file"].strip() or None,
        }

        coa = existing_by_code.get(code)
        if coa is None:
            session.add(ProductCoa(verify_code=code, is_published=publish, **facts))
            inserted += 1
            if not publish:
                inserted_unpublished += 1
            continue

        changed = False
        for attr, value in facts.items():
            if getattr(coa, attr) != value:
                setattr(coa, attr, value)
                changed = True
        if reset_published and coa.is_published != publish:
            coa.is_published = publish
            changed = True
        if changed:
            updated += 1
        else:
            unchanged += 1

    orphaned = sorted(code for code in existing_by_code if code not in manifest_codes)
    return SyncReport(
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
        skipped_unknown_slug=skipped,
        inserted_unpublished=inserted_unpublished,
        orphaned_codes=orphaned,
    )


def _resolve_manifest(arg: Path | None) -> Path:
    if arg is not None:
        return arg
    return default_manifest_path()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument(
        "--publish-client",
        action="append",
        dest="publish_clients",
        help=f"Client name(s) whose NEW certificates are published (default: {', '.join(DEFAULT_PUBLISH_CLIENTS)})",
    )
    parser.add_argument(
        "--reset-published",
        action="store_true",
        help="Also re-derive is_published for EXISTING rows from --publish-client (overrides manual changes).",
    )
    args = parser.parse_args(argv)

    manifest = _resolve_manifest(args.manifest)
    rows = read_manifest(manifest)
    publish_clients = tuple(args.publish_clients) if args.publish_clients else DEFAULT_PUBLISH_CLIENTS

    session = SessionLocal()
    try:
        report = sync_coas(session, rows, publish_clients=publish_clients, reset_published=args.reset_published)
        session.commit()
    finally:
        session.close()

    logger.info(
        "sync_coas: %d manifest rows from %s — inserted=%d (unpublished=%d) updated=%d unchanged=%d",
        len(rows),
        manifest,
        report.inserted,
        report.inserted_unpublished,
        report.updated,
        report.unchanged,
    )
    for entry in report.skipped_unknown_slug:
        logger.warning("skipped, no product with that slug: %s", entry)
    for code in report.orphaned_codes:
        logger.warning("orphan: product_coas row %s is no longer in the manifest (left in place)", code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
