"""Tests for data/sync."""

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ["TRADING_DATABASE_URL"] = "sqlite:///:memory:"

from data.sync import _ms_to_datetime, sync_underlying_bars, sync_options_chain_and_bars


def test_ms_to_datetime():
    # 2024-01-15 12:00:00 UTC = 1705312800000 ms
    dt = _ms_to_datetime(1705312800000)
    assert dt.year == 2024 and dt.month == 1 and dt.day == 15
    assert dt.tzinfo is None


@patch("data.sync.get_massive_client")
def test_sync_underlying_bars_mock(mock_get_client, fresh_storage):
    os.environ["MASSIVE_API_KEY"] = "key"
    mock_client = MagicMock()
    agg = MagicMock()
    agg.timestamp = 1705312800000
    agg.t = None
    agg.open = 100.0
    agg.high = 101.0
    agg.low = 99.0
    agg.close = 100.5
    agg.volume = 1000
    mock_client.list_aggs.return_value = [agg]
    mock_get_client.return_value = mock_client

    n = sync_underlying_bars("AAPL", "2024-01-01", "2024-12-31")
    assert n == 1
    mock_client.list_aggs.assert_called_once()


def test_sync_underlying_bars_no_key_raises(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="MASSIVE_API_KEY"):
        sync_underlying_bars("AAPL", "2024-01-01", "2024-12-31")


@patch("data.sync.get_massive_client")
def test_sync_underlying_bars_uses_t_if_no_timestamp(mock_get_client, fresh_storage):
    os.environ["MASSIVE_API_KEY"] = "key"
    mock_client = MagicMock()
    agg = MagicMock()
    agg.timestamp = None
    agg.t = 1705312800000
    agg.open = 100.0
    agg.high = 101.0
    agg.low = 99.0
    agg.close = 100.5
    agg.volume = 500
    mock_client.list_aggs.return_value = [agg]
    mock_get_client.return_value = mock_client
    n = sync_underlying_bars("AAPL", "2024-01-01", "2024-12-31")
    assert n == 1


@patch("data.sync.get_massive_client")
def test_sync_options_chain_and_bars_mock(mock_get_client, fresh_storage):
    os.environ["MASSIVE_API_KEY"] = "key"
    mock_client = MagicMock()
    details = MagicMock()
    details.ticker = "O:AAPL241220C00150000"
    details.expiration_date = "2024-12-20"
    details.strike_price = 150.0
    details.contract_type = "call"
    snap = MagicMock()
    snap.details = details
    mock_client.list_snapshot_options_chain.return_value = [snap]
    agg = MagicMock()
    agg.timestamp = 1705312800000
    agg.t = None
    agg.open = 5.0
    agg.high = 5.5
    agg.low = 4.8
    agg.close = 5.2
    agg.volume = 100
    mock_client.list_aggs.return_value = [agg]
    mock_get_client.return_value = mock_client
    contracts, bars = sync_options_chain_and_bars("AAPL", "2024-01-01", "2024-12-31", max_contracts=1)
    assert contracts == 1
    assert bars == 1
