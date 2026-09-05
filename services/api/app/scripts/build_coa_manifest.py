"""Manual entrypoint:

    pip install '.[coa]'                                   # pypdf, one-time
    python -m app.scripts.build_coa_manifest "/path/to/Timechain COAs"

Turns the folder of Certificate of Analysis PDFs David receives from the
supplier into services/api/data/coa/coa_manifest.csv — the committed, human-reviewable
record that app.scripts.sync_coas loads into `product_coas`.

Why a manifest rather than reading the PDFs at sync time: the PDFs are
~400 MB and stay out of git; the lab (Accumark Labs) hosts every
certificate publicly at a URL derived from its verification code, and the
storefront links there. What the site needs from each PDF is a handful of
facts — which product, which strength, which lot, when it was certified,
which assays it carries — and this script extracts those ONCE, from the
certificate's own text, into a diff-able CSV. Every row is traceable to a
verification code the customer can check with the lab.

Every fact comes from the certificate, not from the filename or from any
spreadsheet: the strength is the lab's "SAMPLE SIZE", the date is the
lab's "PUBLISHED DATE", the assays are the rows on the certificate. The
filename supplies only the lot and verification code, and both are
verified to appear in the PDF text — a mismatch fails the whole run rather
than silently mislabelling a certificate.

Folder → product mapping is explicit (_FOLDER_TO_SLUG). An unknown folder
is an error, not a guess. The four GLP-class code-name products
(lib/compliance.ts) map by their catalog slug; the manifest carries slugs
only, never the folder names, so nothing this writes reaches a public
surface under any name other than the catalog's.

Idempotent — regenerates the whole manifest from the folder each run.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# The lab's public copy of each certificate, and its verification page.
# Both keyed by the verification code printed on the certificate.
PDF_URL_TEMPLATE = "https://accumark-coa-private-west1.s3.us-west-1.amazonaws.com/coa/{code}.pdf"
VERIFY_URL_TEMPLATE = "https://accumarklabs.com/accuverify/?accuverify_code={code}"

MANIFEST_COLUMNS = [
    "slug",
    "verify_code",
    "strength",
    "lot",
    "issued_on",
    "received_on",
    "lab",
    "client",
    "tests",
    "pdf_url",
    "verify_url",
    "source_file",
]

# Folder name in David's COA folder -> catalog Product.slug. Deliberately a
# closed list: a new folder must be mapped here by hand before it lands
# on a product page.
_FOLDER_TO_SLUG: dict[str, str] = {
    "AOD-9604": "aod-9604",
    "BAC Water": "bac-water",
    "BPC-157": "bpc-157",
    "Cagrilinitide": "cagrilinitide",
    "DSIP": "dsip",
    "Epithalon": "epithalon",
    "GHK-Cu": "ghk-cu",
    "GHK-Cu-KPV": "ghk-cu-kpv",
    "GLOW": "glow-bpc-157-tb-500-ghk",
    "Hexarelin": "hexarelin",
    "IGF1-LR3": "igf1-lr3",
    "Ipamorelin": "ipamorelin",
    "KLOW": "klow-kpv-bpc-157-tb-500-ghk",
    "KPV": "kpv",
    "MOTS-C": "mots-c",
    "MT-1": "mt-1",
    "MT-2": "mt-2",
    "NAD+": "nad",
    "PT-141": "pt-141",
    "Retatrutide": "glp-3r",
    "Selank": "selank",
    "Semaglutide": "glp-1s",
    "Semax": "semax",
    "Sermorelin": "sermorelin",
    "SS-31": "ss-31",
    "TA-1": "ta-1",
    "TB-500": "tb-500",
    "Tesamorelin": "tesamorelin",
    "Tirzepatide": "glp-2t",
    "Wolverine": "bpc-157-tb-500-wolverine",
}

# Blends are certified as one vial with one total mass; the catalog keys
# their variants by per-component strength (ProductVariant.size_key,
# e.g. "10/10/50"). Map the certified total back to that key so the
# Lab report card lines up with the strength picker. A total with no
# entry here stays as the plain mg figure — a blend size we don't sell,
# still a real certificate for the compound.
_BLEND_SIZE_KEY_BY_TOTAL: dict[str, dict[str, str]] = {
    "glow-bpc-157-tb-500-ghk": {"70": "10/10/50"},
    "klow-kpv-bpc-157-tb-500-ghk": {"80": "10/10/10/50"},
    "bpc-157-tb-500-wolverine": {"20": "10/10"},
    "ghk-cu-kpv": {"60": "50/10"},
}

# Substrings that identify the lab and the client named on the
# certificate. Anything else fails loudly — a certificate from a lab we
# have never seen should be looked at by a person, not auto-published.
_LABS = {"accumark": "Accumark Labs"}
_CLIENTS = {"nxgen": "NxGen Bio Med", "valor": "Valor Peptides"}

# (needle in certificate text, display label). Needles for the three
# HPLC rows are upper-case on purpose: the certificate header also says
# "Declared Identity" / "Total Blend purity", which are labels, not
# assays.
_TESTS: list[tuple[str, str, bool]] = [
    ("IDENTITY", "Identity", True),
    ("PURITY", "Purity (HPLC)", True),
    ("QUANTITY", "Quantity", True),
    ("Endotoxin (LAL)", "Endotoxin (LAL)", False),
    ("Rapid Sterility Screening", "Sterility (PCR)", False),
    ("Benzyl Alcohol Assay", "Benzyl alcohol assay (HPLC)", False),
    ("Fill volume", "Fill volume", False),
    ("pH Determination", "pH", False),
]

_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_SIZE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(mg|mL)\b", re.IGNORECASE)
_FILENAME_RE = re.compile(r"^(?P<lot>.+?)__(?P<sku>[^_]+)__(?P<code>[A-Z0-9]{4}-[A-Z0-9]{4})\.pdf$")


class ManifestError(RuntimeError):
    """A certificate could not be read unambiguously. Fails the run —
    nothing about a COA should be guessed."""


@dataclass(frozen=True)
class SourceFilename:
    lot: str
    supplier_sku: str | None
    verify_code: str


@dataclass(frozen=True)
class CertificateFacts:
    lab: str
    client: str
    received_on: date
    issued_on: date
    sample_size: str  # e.g. "60.0 mg", "10 mL" — verbatim from the certificate
    tests: list[str]


@dataclass(frozen=True)
class ManifestRow:
    slug: str
    verify_code: str
    strength: str
    lot: str
    issued_on: date
    received_on: date
    lab: str
    client: str
    tests: list[str]
    pdf_url: str
    verify_url: str
    source_file: str


def parse_source_filename(name: str, folder: str) -> SourceFilename:
    """`{lot}__{supplier_sku}__{verify_code}.pdf`; the SKU segment is
    "nosku" when the supplier's export had none. One file carries the
    folder name as a prefix on the lot ("BAC Water ARC-BW-007"); the lot
    code on the certificate itself never does, so strip it."""
    match = _FILENAME_RE.match(name)
    if match is None:
        raise ManifestError(f"{folder}/{name}: filename is not lot__sku__code.pdf")
    lot = match.group("lot").strip().removeprefix(f"{folder} ")
    sku = match.group("sku")
    return SourceFilename(
        lot=lot,
        supplier_sku=None if sku.lower() == "nosku" else sku,
        verify_code=match.group("code"),
    )


def parse_certificate_text(text: str, *, source: str) -> CertificateFacts:
    """Extract the facts the storefront shows from a certificate's text.

    Date order on an Accumark certificate is received, published, then the
    two signature dates — the first two are the ones that matter.
    "SAMPLE SIZE" is the first mg/mL figure on the page (the measured
    quantity comes after it)."""
    lowered = text.lower()

    lab = next((label for needle, label in _LABS.items() if needle in lowered), None)
    if lab is None:
        raise ManifestError(f"{source}: no recognised lab on the certificate")
    client = next((label for needle, label in _CLIENTS.items() if needle in lowered), None)
    if client is None:
        raise ManifestError(f"{source}: no recognised client on the certificate")

    dates = _DATE_RE.findall(text)
    if len(dates) < 2:
        raise ManifestError(f"{source}: expected received + published dates, found {len(dates)}")
    received_on = _to_date(dates[0], source)
    issued_on = _to_date(dates[1], source)
    if issued_on < received_on:
        raise ManifestError(f"{source}: published date {issued_on} precedes received date {received_on}")

    size = _SIZE_RE.search(text)
    if size is None:
        raise ManifestError(f"{source}: no sample size on the certificate")
    unit = "mL" if size.group(2).lower() == "ml" else "mg"
    sample_size = f"{size.group(1)} {unit}"

    tests = [
        label
        for needle, label, case_sensitive in _TESTS
        if ((needle in text) if case_sensitive else (needle.lower() in lowered))
    ]
    if not tests:
        raise ManifestError(f"{source}: no recognised assays on the certificate")

    return CertificateFacts(
        lab=lab,
        client=client,
        received_on=received_on,
        issued_on=issued_on,
        sample_size=sample_size,
        tests=tests,
    )


def _to_date(parts: tuple[str, str, str], source: str) -> date:
    month, day, year = parts
    try:
        return date(int(year), int(month), int(day))
    except ValueError as exc:
        raise ManifestError(f"{source}: bad date {month}/{day}/{year}") from exc


def normalize_strength(sample_size: str, slug: str) -> str:
    """Certificate "60.0 mg" -> "60"; "10 mL" -> "10mL" — the same shape
    as ProductVariant.size_key, so the Lab report cards line up with the
    strength picker (and formatStrength() on the frontend renders both).
    Blend totals map back to the per-component key, see
    _BLEND_SIZE_KEY_BY_TOTAL."""
    amount, unit = sample_size.split()
    if "." in amount:
        amount = amount.rstrip("0").rstrip(".")
    if unit == "mL":
        return f"{amount}mL"
    return _BLEND_SIZE_KEY_BY_TOTAL.get(slug, {}).get(amount, amount)


def _strength_sort_key(strength: str) -> tuple[float, str]:
    match = re.match(r"\d+(?:\.\d+)?", strength)
    return (float(match.group(0)) if match else float("inf"), strength)


def _read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover — environment, not logic
        raise SystemExit("pypdf is required: pip install '.[coa]'") from exc
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def build_rows(source_dir: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    seen_codes: dict[str, str] = {}
    for folder in sorted(p for p in source_dir.iterdir() if p.is_dir()):
        slug = _FOLDER_TO_SLUG.get(folder.name)
        if slug is None:
            raise ManifestError(f"unmapped folder {folder.name!r} — add it to _FOLDER_TO_SLUG")
        for pdf in sorted(folder.glob("*.pdf")):
            source = f"{folder.name}/{pdf.name}"
            named = parse_source_filename(pdf.name, folder.name)
            text = _read_pdf_text(pdf)
            if named.verify_code not in text:
                raise ManifestError(f"{source}: verification code {named.verify_code} not found in the certificate")
            if named.lot not in text:
                raise ManifestError(f"{source}: lot {named.lot} not found in the certificate")
            if named.verify_code in seen_codes:
                raise ManifestError(f"{source}: duplicate verification code, also in {seen_codes[named.verify_code]}")
            seen_codes[named.verify_code] = source

            facts = parse_certificate_text(text, source=source)
            rows.append(
                ManifestRow(
                    slug=slug,
                    verify_code=named.verify_code,
                    strength=normalize_strength(facts.sample_size, slug),
                    lot=named.lot,
                    issued_on=facts.issued_on,
                    received_on=facts.received_on,
                    lab=facts.lab,
                    client=facts.client,
                    tests=facts.tests,
                    pdf_url=PDF_URL_TEMPLATE.format(code=named.verify_code),
                    verify_url=VERIFY_URL_TEMPLATE.format(code=named.verify_code),
                    source_file=pdf.name,
                )
            )
    rows.sort(key=lambda r: (r.slug, _strength_sort_key(r.strength), r.issued_on, r.verify_code))
    return rows


def write_manifest(rows: list[ManifestRow], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "slug": row.slug,
                    "verify_code": row.verify_code,
                    "strength": row.strength,
                    "lot": row.lot,
                    "issued_on": row.issued_on.isoformat(),
                    "received_on": row.received_on.isoformat(),
                    "lab": row.lab,
                    "client": row.client,
                    "tests": "|".join(row.tests),
                    "pdf_url": row.pdf_url,
                    "verify_url": row.verify_url,
                    "source_file": row.source_file,
                }
            )


def default_manifest_path() -> Path:
    """services/api/data/coa/coa_manifest.csv (this file lives at
    services/api/app/scripts/, two levels down). It lives inside the API
    package so the Vercel build — which uploads services/api only — can
    load it (scripts/vercel-build.sh)."""
    return Path(__file__).resolve().parents[2] / "data" / "coa" / "coa_manifest.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source_dir", type=Path, help="Folder of per-product subfolders of certificate PDFs")
    parser.add_argument("--out", type=Path, default=default_manifest_path())
    args = parser.parse_args(argv)

    try:
        rows = build_rows(args.source_dir)
    except ManifestError as exc:
        logger.error("%s", exc)
        return 1

    write_manifest(rows, args.out)

    by_slug: dict[str, int] = {}
    by_client: dict[str, int] = {}
    for row in rows:
        by_slug[row.slug] = by_slug.get(row.slug, 0) + 1
        by_client[row.client] = by_client.get(row.client, 0) + 1
    logger.info("wrote %d certificates for %d products to %s", len(rows), len(by_slug), args.out)
    for slug, count in sorted(by_slug.items()):
        logger.info("  %-32s %3d", slug, count)
    for client, count in sorted(by_client.items()):
        logger.info("client %-20s %3d", client, count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
