import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _ordering_enabled_for_tests(monkeypatch):
    """ORDERING_ENABLED defaults to False (the combined site takes no
    orders), which would 503 every checkout test. Turn it on for the
    suite; tests/test_ordering_flag.py flips it back off to cover the
    refusal itself."""
    monkeypatch.setattr(get_settings(), "ordering_enabled", True)
