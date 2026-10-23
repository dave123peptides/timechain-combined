import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _combined_site_switches_for_tests(monkeypatch):
    """Two switches default to the showcase site's safe values and would
    otherwise break the inherited checkout and catalog tests: ordering
    off (checkout answers 503) and prices hidden (price fields null).
    Turn both on for the suite; tests/test_ordering_flag.py and
    tests/test_catalog_prices.py flip them back to cover the defaults."""
    monkeypatch.setattr(get_settings(), "ordering_enabled", True)
    monkeypatch.setattr(get_settings(), "catalog_prices_public", True)
