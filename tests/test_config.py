"""Tests for config/settings."""

from config.settings import (
    get_massive_api_key,
    get_etrade_consumer_key,
    get_etrade_consumer_secret,
    get_etrade_access_token,
    get_etrade_access_secret,
    get_etrade_sandbox,
    get_database_url,
    get_sync_default_symbol,
    get_sync_date_from,
    get_sync_date_to,
)


def test_get_massive_api_key(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    assert get_massive_api_key() is None
    monkeypatch.setenv("MASSIVE_API_KEY", "testkey")
    assert get_massive_api_key() == "testkey"


def test_get_etrade_consumer_key(monkeypatch):
    monkeypatch.delenv("ETrade_CONSUMER_KEY", raising=False)
    assert get_etrade_consumer_key() is None
    monkeypatch.setenv("ETrade_CONSUMER_KEY", "ck")
    assert get_etrade_consumer_key() == "ck"


def test_get_etrade_consumer_secret(monkeypatch):
    monkeypatch.setenv("ETrade_CONSUMER_SECRET", "cs")
    assert get_etrade_consumer_secret() == "cs"


def test_get_etrade_access_token(monkeypatch):
    monkeypatch.setenv("ETrade_ACCESS_TOKEN", "at")
    assert get_etrade_access_token() == "at"


def test_get_etrade_access_secret(monkeypatch):
    monkeypatch.setenv("ETrade_ACCESS_SECRET", "ats")
    assert get_etrade_access_secret() == "ats"


def test_get_etrade_sandbox_default(monkeypatch):
    monkeypatch.delenv("ETrade_SANDBOX", raising=False)
    assert get_etrade_sandbox() is True


def test_get_etrade_sandbox_false(monkeypatch):
    monkeypatch.setenv("ETrade_SANDBOX", "false")
    assert get_etrade_sandbox() is False
    monkeypatch.setenv("ETrade_SANDBOX", "0")
    assert get_etrade_sandbox() is False


def test_get_database_url_default(monkeypatch):
    monkeypatch.delenv("TRADING_DATABASE_URL", raising=False)
    url = get_database_url()
    assert "sqlite" in url and "trading.db" in url


def test_get_database_url_override(monkeypatch):
    monkeypatch.setenv("TRADING_DATABASE_URL", "sqlite:///custom.db")
    assert get_database_url() == "sqlite:///custom.db"


def test_get_sync_default_symbol(monkeypatch):
    monkeypatch.delenv("TRADING_DEFAULT_SYMBOL", raising=False)
    assert get_sync_default_symbol() == "AAPL"
    monkeypatch.setenv("TRADING_DEFAULT_SYMBOL", "MSFT")
    assert get_sync_default_symbol() == "MSFT"


def test_get_sync_date_from_to(monkeypatch):
    assert get_sync_date_from() == "2024-01-01"
    assert get_sync_date_to() == "2024-12-31"
    monkeypatch.setenv("TRADING_SYNC_FROM", "2025-01-01")
    monkeypatch.setenv("TRADING_SYNC_TO", "2025-06-01")
    assert get_sync_date_from() == "2025-01-01"
    assert get_sync_date_to() == "2025-06-01"
