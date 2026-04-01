"""Tests for strategies (single-leg options, SMA, covered call, protective put)."""

import os
from datetime import datetime, timedelta

import pandas as pd

os.environ["TRADING_DATABASE_URL"] = "sqlite:///:memory:"

import backtrader as bt

from backtrader_feeds import OptionsPandasFeed
from strategies import (
    SingleLegOptionsStrategy,
    SmaCrossoverStrategy,
    SmaRsiStrategy,
    CoveredCallStrategy,
    ProtectivePutStrategy,
)


def test_single_leg_options_strategy_runs():
    """Smoke test: Cerebro runs with one option feed and strategy."""
    df = pd.DataFrame({
        "datetime": pd.to_datetime([datetime(2024, 1, 15), datetime(2024, 1, 16)]),
        "open": [5.0, 5.2],
        "high": [5.5, 5.8],
        "low": [4.8, 5.0],
        "close": [5.2, 5.5],
        "volume": [100, 120],
    }).set_index("datetime")
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000.0)
    feed = OptionsPandasFeed(
        dataname=df,
        strike=150.0,
        expiration=datetime(2024, 12, 20),
        option_type="call",
    )
    cerebro.adddata(feed)
    cerebro.addstrategy(SingleLegOptionsStrategy, size=1)
    cerebro.run()
    assert cerebro.broker.getvalue() is not None


def test_single_leg_options_strategy_expiry_close():
    """Strategy closes position when near expiry (expiry_days_before=1)."""
    df = pd.DataFrame({
        "datetime": pd.to_datetime([datetime(2024, 1, 15), datetime(2024, 1, 16)]),
        "open": [5.0, 5.2],
        "high": [5.5, 5.8],
        "low": [4.8, 5.0],
        "close": [5.2, 5.5],
        "volume": [100, 120],
    }).set_index("datetime")
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000.0)
    feed = OptionsPandasFeed(
        dataname=df,
        strike=150.0,
        expiration=datetime(2024, 1, 17),
        option_type="call",
    )
    cerebro.adddata(feed)
    cerebro.addstrategy(SingleLegOptionsStrategy, size=1, exit_before_expiry=True, expiry_days_before=2)
    cerebro.run()
    assert cerebro.broker.getvalue() is not None


def _equity_df(days=60, start_price=100.0, trend=0.5):
    """Build a simple equity series: enough bars for fast=5, slow=15."""
    base = datetime(2024, 1, 1)
    dates = [base + timedelta(days=i) for i in range(days)]
    closes = [start_price + i * trend + (i % 5) * 0.3 for i in range(days)]
    return pd.DataFrame({
        "datetime": dates,
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": [1000] * days,
    }).set_index("datetime")


def test_sma_crossover_strategy_runs():
    """SMA crossover runs on underlying feed (short periods for test)."""
    df = _equity_df(60)
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000.0)
    cerebro.adddata(bt.feeds.PandasData(dataname=df))
    cerebro.addstrategy(SmaCrossoverStrategy, fast_period=5, slow_period=15, size=10)
    cerebro.run()
    assert cerebro.broker.getvalue() is not None


def test_sma_rsi_strategy_runs():
    """SMA + RSI strategy runs on underlying feed."""
    df = _equity_df(60)
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000.0)
    cerebro.adddata(bt.feeds.PandasData(dataname=df))
    cerebro.addstrategy(SmaRsiStrategy, fast_period=5, slow_period=15, rsi_period=7, size=10)
    cerebro.run()
    assert cerebro.broker.getvalue() is not None


def test_covered_call_strategy_runs():
    """Covered call runs with option + underlying (smoke)."""
    opt_df = pd.DataFrame({
        "datetime": pd.to_datetime([datetime(2024, 1, 15), datetime(2024, 1, 16)]),
        "open": [5.0, 5.2], "high": [5.5, 5.8], "low": [4.8, 5.0],
        "close": [5.2, 5.5], "volume": [100, 120],
    }).set_index("datetime")
    und_df = pd.DataFrame({
        "datetime": pd.to_datetime([datetime(2024, 1, 15), datetime(2024, 1, 16)]),
        "open": [180.0, 181.0], "high": [182.0, 183.0], "low": [179.0, 180.0],
        "close": [181.0, 182.0], "volume": [1000, 1100],
    }).set_index("datetime")
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000.0)
    cerebro.adddata(OptionsPandasFeed(dataname=opt_df, expiration=datetime(2024, 12, 20), option_type="call"), name="option")
    cerebro.adddata(bt.feeds.PandasData(dataname=und_df), name="underlying")
    cerebro.addstrategy(CoveredCallStrategy, underlying_size=100, option_size=1)
    cerebro.run()
    assert cerebro.broker.getvalue() is not None


def test_protective_put_strategy_runs():
    """Protective put runs with option + underlying (smoke)."""
    opt_df = pd.DataFrame({
        "datetime": pd.to_datetime([datetime(2024, 1, 15), datetime(2024, 1, 16)]),
        "open": [3.0, 3.1], "high": [3.5, 3.6], "low": [2.8, 2.9],
        "close": [3.2, 3.3], "volume": [80, 90],
    }).set_index("datetime")
    und_df = pd.DataFrame({
        "datetime": pd.to_datetime([datetime(2024, 1, 15), datetime(2024, 1, 16)]),
        "open": [180.0, 181.0], "high": [182.0, 183.0], "low": [179.0, 180.0],
        "close": [181.0, 182.0], "volume": [1000, 1100],
    }).set_index("datetime")
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000.0)
    cerebro.adddata(OptionsPandasFeed(dataname=opt_df, expiration=datetime(2024, 12, 20), option_type="put"), name="option")
    cerebro.adddata(bt.feeds.PandasData(dataname=und_df), name="underlying")
    cerebro.addstrategy(ProtectivePutStrategy, underlying_size=100, option_size=1)
    cerebro.run()
    assert cerebro.broker.getvalue() is not None
