"""Unit tests for backtrader feed helpers (bars_to_dataframe, etc.)."""

from datetime import datetime

import pandas as pd

from backtrader_feeds import bars_to_dataframe, dataframe_from_storage_bars, underlying_bars_to_dataframe


def test_bars_to_dataframe_from_dicts() -> None:
    bars = [
        {"datetime": datetime(2024, 1, 15), "open": 5.0, "high": 5.5, "low": 4.8, "close": 5.2, "volume": 100},
        {"datetime": datetime(2024, 1, 16), "open": 5.2, "high": 5.8, "low": 5.0, "close": 5.5, "volume": 120},
    ]
    df = bars_to_dataframe(bars)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df["close"].values) == [5.2, 5.5]


def test_bars_to_dataframe_from_orm_like() -> None:
    class Bar:
        def __init__(self, dt, o, h, low, c, v, oi=None, iv=None):
            self.datetime = dt
            self.open = o
            self.high = h
            self.low = low
            self.close = c
            self.volume = v
            self.open_interest = oi
            self.implied_volatility = iv

    bars = [
        Bar(datetime(2024, 1, 15), 5.0, 5.5, 4.8, 5.2, 100, oi=500, iv=0.25),
    ]
    df = dataframe_from_storage_bars(bars)
    assert len(df) == 1
    assert df.shape[0] == 1
    # Optional columns if present on bar objects
    assert "close" in df.columns


def test_underlying_bars_to_dataframe() -> None:
    class Bar:
        def __init__(self, dt, o, h, low, c, v):
            self.datetime = dt
            self.open = o
            self.high = h
            self.low = low
            self.close = c
            self.volume = v

    bars = [
        Bar(datetime(2024, 1, 15), 180.0, 182.0, 179.0, 181.0, 1_000_000),
    ]
    df = underlying_bars_to_dataframe(bars)
    assert len(df) == 1
    assert df["close"].iloc[0] == 181.0
