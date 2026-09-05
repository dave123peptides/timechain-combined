from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models.catalog import Product, ProductCoa
from app.scripts import sync_coas
from app.scripts.build_coa_manifest import (
    MANIFEST_COLUMNS,
    ManifestError,
    normalize_strength,
    parse_certificate_text,
    parse_source_filename,
)

_TEST_SLUG = "test-coa-sync-product"
_CODES = ("TSYN-0001", "TSYN-0002", "TSYN-0003")


def _cleanup(session):
    session.execute(text("DELETE FROM product_coas WHERE verify_code = ANY(:codes)"), {"codes": list(_CODES)})
    session.execute(text("DELETE FROM products WHERE slug = :slug"), {"slug": _TEST_SLUG})
    session.commit()


@pytest.fixture
def session():
    db = SessionLocal()
    _cleanup(db)
    product = Product(slug=_TEST_SLUG, name="Test COA Sync Product", images=[], is_active=False)
    db.add(product)
    db.commit()
    yield db
    db.rollback()
    _cleanup(db)
    db.close()


def _row(code, *, slug=_TEST_SLUG, client="NxGen Bio Med", lot="ARC-X-001", issued="2026-07-17", strength="10"):
    return {
        "slug": slug,
        "verify_code": code,
        "strength": strength,
        "lot": lot,
        "issued_on": issued,
        "received_on": "2026-07-01",
        "lab": "Accumark Labs",
        "client": client,
        "tests": "Identity|Purity (HPLC)|Quantity",
        "pdf_url": f"https://example.invalid/coa/{code}.pdf",
        "verify_url": f"https://example.invalid/verify?code={code}",
        "source_file": f"{lot}__SKU-10__{code}.pdf",
    }


def _coa(session, code):
    return session.execute(select(ProductCoa).where(ProductCoa.verify_code == code)).scalar_one_or_none()


# --- sync -----------------------------------------------------------------


def test_sync_inserts_publishes_by_client_and_is_idempotent(session):
    rows = [
        _row(_CODES[0]),
        _row(_CODES[1], client="Valor Peptides", lot="BP2002"),
        _row(_CODES[2], slug="no-such-product"),
    ]
    report = sync_coas.sync_coas(session, rows)
    session.flush()

    assert report.inserted == 2
    assert report.inserted_unpublished == 1
    assert report.skipped_unknown_slug == [f"no-such-product ({_CODES[2]})"]
    ours = _coa(session, _CODES[0])
    assert ours.is_published is True
    assert ours.issued_on == date(2026, 7, 17)
    assert ours.tests == ["Identity", "Purity (HPLC)", "Quantity"]
    assert ours.strength == "10"
    theirs = _coa(session, _CODES[1])
    assert theirs.is_published is False
    assert _coa(session, _CODES[2]) is None

    again = sync_coas.sync_coas(session, rows)
    assert (again.inserted, again.updated, again.unchanged) == (0, 0, 2)


def test_sync_updates_facts_but_never_flips_a_manual_publish_decision(session):
    sync_coas.sync_coas(session, [_row(_CODES[0])])
    session.flush()
    coa = _coa(session, _CODES[0])
    coa.is_published = False  # a person hid it
    session.flush()

    report = sync_coas.sync_coas(session, [_row(_CODES[0], lot="ARC-X-001-CORRECTED")])
    session.flush()
    assert report.updated == 1
    coa = _coa(session, _CODES[0])
    assert coa.lot == "ARC-X-001-CORRECTED"
    assert coa.is_published is False

    # Only an explicit --reset-published re-derives the flag.
    sync_coas.sync_coas(session, [_row(_CODES[0], lot="ARC-X-001-CORRECTED")], reset_published=True)
    session.flush()
    assert _coa(session, _CODES[0]).is_published is True


def test_sync_reports_orphans_without_deleting(session):
    sync_coas.sync_coas(session, [_row(_CODES[0]), _row(_CODES[1])])
    session.flush()

    report = sync_coas.sync_coas(session, [_row(_CODES[0])])
    assert _CODES[1] in report.orphaned_codes
    assert _coa(session, _CODES[1]) is not None


def test_read_manifest_requires_every_column(tmp_path: Path):
    path = tmp_path / "m.csv"
    path.write_text("slug,verify_code\nx,y\n")
    with pytest.raises(ValueError, match="missing columns"):
        sync_coas.read_manifest(path)

    path.write_text(",".join(MANIFEST_COLUMNS) + "\n")
    assert sync_coas.read_manifest(path) == []


# --- manifest builder (pure parsing, no PDFs) ------------------------------


_PEPTIDE_CERT = """ACCUMARKLABS.COM
CERTIFICATE OF ANALYSISccumark Labs
SAMPLE NAME:
NxGen Bio Med
support@nxgenbiomedical.com
AOD-9604
GXZD-ZQ8Z
 04/02/2026
 07/17/2026
Declared Identity
AOD-9604
PEPTIDE
5.0 mg
AO0001
4.97 mg
Total Blend purity
98.83%
IDENTITY
CONFORMS
QUANTITY
MEASURE
PURITY
> 98.0%
Endotoxin (LAL)
Rapid Sterility Screening
 (PCR)
"""

_WATER_CERT = """CERTIFICATE OF ANALYSIS
ccumark Labs
ACCUMARKLABS.COM
NxGen Bio Med
Bacteriostatic Water
 ADYG-2FSR
 06/10/2026
06/18/2026
Declared Identity
Bacteriostatic Water
10 mL
ARC-BW-012
Benzyl Alcohol Assay
 (HPLC)
Fill volume / Net content
pH Determination
Endotoxin (LAL)
Rapid Sterility Screening
"""


def test_parse_peptide_certificate():
    facts = parse_certificate_text(_PEPTIDE_CERT, source="t")
    assert facts.lab == "Accumark Labs"
    assert facts.client == "NxGen Bio Med"
    assert facts.received_on == date(2026, 4, 2)
    assert facts.issued_on == date(2026, 7, 17)
    assert facts.sample_size == "5.0 mg"
    # "Declared Identity" / "Total Blend purity" are labels, not assays.
    assert facts.tests == ["Identity", "Purity (HPLC)", "Quantity", "Endotoxin (LAL)", "Sterility (PCR)"]


def test_parse_water_certificate():
    facts = parse_certificate_text(_WATER_CERT, source="t")
    assert facts.sample_size == "10 mL"
    assert facts.tests == [
        "Endotoxin (LAL)",
        "Sterility (PCR)",
        "Benzyl alcohol assay (HPLC)",
        "Fill volume",
        "pH",
    ]


def test_parse_certificate_fails_loudly_on_unknown_lab_or_client():
    with pytest.raises(ManifestError, match="no recognised lab"):
        parse_certificate_text(_PEPTIDE_CERT.replace("ccumark", "Other").replace("ACCUMARKLABS", "X"), source="t")
    with pytest.raises(ManifestError, match="no recognised client"):
        parse_certificate_text(
            _PEPTIDE_CERT.replace("NxGen Bio Med", "Someone Else").replace("support@nxgenbiomedical.com", "x@y"),
            source="t",
        )


def test_parse_source_filename():
    named = parse_source_filename("ARC-RT60-002__RT-60__7XR9-HHV9.pdf", "Retatrutide")
    assert (named.lot, named.supplier_sku, named.verify_code) == ("ARC-RT60-002", "RT-60", "7XR9-HHV9")
    nosku = parse_source_filename("BAC Water ARC-BW-007__nosku__PKF2-DLRL.pdf", "BAC Water")
    assert (nosku.lot, nosku.supplier_sku) == ("ARC-BW-007", None)
    with pytest.raises(ManifestError):
        parse_source_filename("random.pdf", "X")


def test_normalize_strength_matches_variant_size_keys():
    assert normalize_strength("60.0 mg", "glp-3r") == "60"
    assert normalize_strength("1.0 mg", "igf1-lr3") == "1"
    assert normalize_strength("10 mL", "bac-water") == "10mL"
    assert normalize_strength("70.0 mg", "glow-bpc-157-tb-500-ghk") == "10/10/50"
    assert normalize_strength("20.0 mg", "bpc-157-tb-500-wolverine") == "10/10"
    # A blend size we don't sell stays as the certified total.
    assert normalize_strength("90.0 mg", "glow-bpc-157-tb-500-ghk") == "90"
