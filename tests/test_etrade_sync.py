"""Tests for data/etrade_sync."""

from unittest.mock import patch

import pytest

from data.etrade_sync import (
    _now_normalized,
    _float,
    _int,
    sync_etrade_quotes,
    sync_etrade_option_chain,
    sync_etrade_option_expirations,
)


def test_now_normalized():
    dt = _now_normalized()
    assert dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0


def test_float_helper():
    assert _float(1.5) == 1.5
    assert _float("2.5") == 2.5
    assert _float(None, 0.0) == 0.0
    assert _float("x", 1.0) == 1.0


def test_int_helper():
    assert _int(10) == 10
    assert _int(None, 0) == 0
    assert _int("x", 5) == 5


def test_sync_etrade_quotes_no_creds(monkeypatch):
    monkeypatch.delenv("ETrade_CONSUMER_KEY", raising=False)
    with pytest.raises(ValueError, match="E*TRADE credentials"):
        sync_etrade_quotes(["AAPL"])


@patch("data.etrade_sync.get_quotes")
def test_sync_etrade_quotes_mock(mock_get_quotes, fresh_storage, etrade_env):
    mock_get_quotes.return_value = {
        "QuoteResponse": {
            "QuoteData": [
                {"symbol": "AAPL", "All": {"open": 180, "high": 182, "low": 179, "lastTrade": 181, "volume": 1000}},
            ]
        }
    }
    n = sync_etrade_quotes(["AAPL"])
    assert n == 1


@patch("data.etrade_sync.get_option_chain")
def test_sync_etrade_option_chain_mock(mock_get_chain, fresh_storage, etrade_env):
    mock_get_chain.return_value = {
        "OptionChainResponse": {
            "OptionPair": [
                {
                    "Call": [
                        {"symbol": "AAPL241220C00150000", "strikePrice": 150, "expiryDate": "2024-12-20", "lastPrice": 5.0, "volume": 10},
                    ],
                    "Put": [],
                }
            ]
        }
    }
    contracts, bars = sync_etrade_option_chain("AAPL", expiry_date="2024-12-20")
    assert contracts >= 1
    assert bars >= 1


def test_sync_etrade_option_expirations_no_creds(monkeypatch):
    monkeypatch.delenv("ETrade_CONSUMER_KEY", raising=False)
    with pytest.raises(ValueError, match="E*TRADE credentials"):
        sync_etrade_option_expirations("AAPL")


@patch("data.etrade_sync.get_option_expire_dates")
def test_sync_etrade_option_expirations_mock(mock_get_dates, etrade_env):
    mock_get_dates.return_value = {"OptionExpireDateResponse": {"ExpirationDate": [{"date": "2024-12-20"}, {"year": 2025, "month": 1, "day": 17}]}}
    result = sync_etrade_option_expirations("AAPL")
    assert "2024-12-20" in result
    assert "2025-01-17" in result


@patch("data.etrade_sync.get_quotes")
def test_sync_etrade_quotes_single_quote_dict(mock_get_quotes, fresh_storage, etrade_env):
    mock_get_quotes.return_value = {
        "QuoteResponse": {"QuoteData": {"symbol": "MSFT", "All": {"open": 400, "high": 402, "low": 399, "lastTrade": 401, "volume": 2000}}}
    }
    n = sync_etrade_quotes(["MSFT"])
    assert n == 1


@patch("data.etrade_sync.get_quotes")
def test_sync_etrade_quotes_nested_product_and_all(mock_get_quotes, fresh_storage, etrade_env):
    mock_get_quotes.return_value = {
        "QuoteResponse": {
            "QuoteData": {
                "product": {"symbol": "TSLA"},
                "all": {
                    "lastTrade": 210.5,
                    "open": 209.0,
                    "high": 212.0,
                    "low": 208.5,
                    "volume": 3210,
                },
            }
        }
    }
    n = sync_etrade_quotes(["TSLA"])
    assert n == 1


@patch("data.etrade_sync.get_quotes")
def test_sync_etrade_quotes_rejects_unexpected_symbol(mock_get_quotes, fresh_storage):
    mock_get_quotes.return_value = {
        "QuoteResponse": {
            "QuoteData": {
                "Product": {"symbol": "GOOG"},
                "All": {"lastTrade": 577.51},
            }
        }
    }
    with pytest.raises(ValueError, match="unexpected symbol"):
        sync_etrade_quotes(
            ["VOO"],
            etrade_credentials={
                "etrade_consumer_key": "ck",
                "etrade_consumer_secret": "cs",
                "etrade_access_token": "at",
                "etrade_access_secret": "ats",
                "etrade_sandbox": True,
            },
        )


@patch("data.etrade_sync.get_option_chain")
def test_sync_etrade_option_chain_put(mock_get_chain, fresh_storage, etrade_env):
    mock_get_chain.return_value = {
        "OptionChainResponse": {
            "OptionPair": [{"Call": [], "Put": [{"symbol": "AAPL241220P00145000", "strikePrice": 145, "expiryDate": "2024-12-20", "lastPrice": 2.0, "volume": 5}]}]
        }
    }
    contracts, bars = sync_etrade_option_chain("AAPL", expiry_date="2024-12-20")
    assert contracts >= 1
    assert bars >= 1
