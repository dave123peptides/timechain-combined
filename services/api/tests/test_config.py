"""Settings behaviour that has bitten production."""

from app.core.config import Settings, _site_origins


def test_site_origins_adds_www_twin_and_strips_path():
    assert _site_origins("https://timechainpeptides.com/") == [
        "https://timechainpeptides.com",
        "https://www.timechainpeptides.com",
    ]
    assert _site_origins("https://www.timechainpeptides.com") == [
        "https://www.timechainpeptides.com",
        "https://timechainpeptides.com",
    ]
    assert _site_origins("") == []
    assert _site_origins("not a url") == []


def test_cors_origins_always_include_the_storefront_origin():
    settings = Settings(api_cors_origins="http://localhost:3000", public_site_url="https://timechainpeptides.com")
    assert settings.cors_origins_list == [
        "http://localhost:3000",
        "https://timechainpeptides.com",
        "https://www.timechainpeptides.com",
    ]


def test_cors_origins_do_not_duplicate_an_explicit_entry():
    settings = Settings(
        api_cors_origins="https://www.timechainpeptides.com/, http://localhost:3000",
        public_site_url="https://www.timechainpeptides.com",
    )
    assert settings.cors_origins_list == [
        "https://www.timechainpeptides.com",
        "http://localhost:3000",
        "https://timechainpeptides.com",
    ]
