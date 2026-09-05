"""The manifest must live inside services/api: the Vercel build uploads
only this directory and scripts/vercel-build.sh syncs it from there."""

import csv
from pathlib import Path

from app.scripts.build_coa_manifest import MANIFEST_COLUMNS, default_manifest_path
from app.scripts.sync_coas import read_manifest


def test_default_manifest_is_inside_the_api_package_and_readable():
    path = default_manifest_path()
    assert path == Path(__file__).resolve().parents[1] / "data" / "coa" / "coa_manifest.csv"
    assert path.exists()
    # The pen catalog has no certificates yet, so the manifest is a header
    # row only — read_manifest must still accept it (an empty file would
    # fail the Vercel build's sync_coas step; a header-only one runs clean).
    with path.open(newline="") as handle:
        fieldnames = csv.DictReader(handle).fieldnames or []
    assert set(MANIFEST_COLUMNS) <= set(fieldnames)
    assert isinstance(read_manifest(path), list)
