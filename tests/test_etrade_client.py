"""Tests for data/etrade_client."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from data.etrade_client import get_etrade_market, get_quotes, get_option_chain, get_option_expire_dates


def test_get_etrade_market_raises_without_creds(monkeypatch):
    monkeypatch.delenv("ETrade_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("ETrade_CONSUMER_SECRET", raising=False)
    monkeypatch.delenv("ETrade_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("ETrade_ACCESS_SECRET", raising=False)
    with pytest.raises(ValueError, match="E*TRADE credentials"):
        get_etrade_market()


def test_get_etrade_market_with_args():
    with patch("data.etrade_client.ETradeMarket") as mock_market:
        get_etrade_market(
            consumer_key="ck",
            consumer_secret="cs",
            access_token="at",
            access_secret="ats",
            sandbox=True,
        )
        mock_market.assert_called_once_with(
            client_key="ck",
            client_secret="cs",
            resource_owner_key="at",
            resource_owner_secret="ats",
            dev=True,
        )


def test_get_quotes(etrade_env):
    with patch("data.etrade_client.get_etrade_market") as mock_get:
        mock_market = MagicMock()
        mock_market.get_quote.return_value = {"QuoteResponse": {"QuoteData": []}}
        mock_get.return_value = mock_market
        result = get_quotes(["AAPL"], resp_format="json")
        assert result == {"QuoteResponse": {"QuoteData": []}}
        mock_market.get_quote.assert_called_once_with(["AAPL"], resp_format="json")


def test_get_option_chain(etrade_env):
    with patch("data.etrade_client.get_etrade_market") as mock_get:
        mock_market = MagicMock()
        mock_market.get_option_chains.return_value = {"OptionChainResponse": {}}
        mock_get.return_value = mock_market
        result = get_option_chain("AAPL", expiry_date="2024-12-20", resp_format="json")
        assert "OptionChainResponse" in result
        mock_market.get_option_chains.assert_called_once_with(
            "AAPL",
            date(2024, 12, 20),
            chain_type="callput",
            strike_price_near=None,
            no_of_strikes=None,
            resp_format="json",
        )


def test_get_option_chain_normalizes_legacy_chain_type(etrade_env):
    with patch("data.etrade_client.get_etrade_market") as mock_get:
        mock_market = MagicMock()
        mock_market.get_option_chains.return_value = {"OptionChainResponse": {}}
        mock_get.return_value = mock_market
        get_option_chain("AAPL", chain_type="call/put", resp_format="json")
        mock_market.get_option_chains.assert_called_once_with(
            "AAPL",
            None,
            chain_type="callput",
            strike_price_near=None,
            no_of_strikes=None,
            resp_format="json",
        )


def test_get_option_expire_dates(etrade_env):
    with patch("data.etrade_client.get_etrade_market") as mock_get:
        mock_market = MagicMock()
        mock_market.get_option_expire_date.return_value = {"OptionExpireDateResponse": {"ExpirationDate": []}}
        mock_get.return_value = mock_market
        result = get_option_expire_dates("AAPL", resp_format="json")
        assert "OptionExpireDateResponse" in result
