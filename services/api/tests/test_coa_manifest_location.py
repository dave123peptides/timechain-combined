"""The manifest must live inside services/api: the Vercel build uploads
only this directory and scripts/vercel-build.sh syncs it from there."""

from pathlib import Path

from app.scripts.build_coa_manifest import MANIFEST_COLUMNS, default_manifest_path
from app.scripts.sync_coas import read_manifest


def test_default_manifest_is_inside_the_api_package_and_readable():
    path = default_manifest_path()
    assert path == Path(__file__).resolve().parents[1] / "data" / "coa" / "coa_manifest.csv"
    assert path.exists()
    rows = read_manifest(path)
    assert rows, "manifest is empty"
    assert set(MANIFEST_COLUMNS) <= set(rows[0].keys())
