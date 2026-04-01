"""Custom Backtrader data feed for options bars (from DataFrame or list of bars)."""

from typing import Any, Sequence

import backtrader as bt
import pandas as pd


class OptionsPandasFeed(bt.feeds.PandasData):
    """
    Options OHLCV feed from a pandas DataFrame. Adds optional implied_volatility line
    and contract metadata (strike, expiration, option_type) in params for strategy use.
    """

    # Optional extra line for implied volatility
    lines = ("implied_vol",)
    params = (
        ("implied_vol", -1),
        ("strike", None),
        ("expiration", None),
        ("option_type", None),
    )


def bars_to_dataframe(
    bars: Sequence[Any],
    *,
    datetime_attr: str = "datetime",
    open_attr: str = "open",
    high_attr: str = "high",
    low_attr: str = "low",
    close_attr: str = "close",
    volume_attr: str = "volume",
    open_interest_attr: str = "open_interest",
    implied_vol_attr: str = "implied_volatility",
) -> pd.DataFrame:
    """Build a DataFrame from a list of options bar objects (ORM or dict-like) for OptionsPandasFeed."""
    rows = []
    for b in bars:
        dt = getattr(b, datetime_attr, None) or b.get(datetime_attr) if isinstance(b, dict) else None
        o = getattr(b, open_attr, None) or (b.get(open_attr) if isinstance(b, dict) else None)
        h = getattr(b, high_attr, None) or (b.get(high_attr) if isinstance(b, dict) else None)
        lo = getattr(b, low_attr, None) or (b.get(low_attr) if isinstance(b, dict) else None)
        c = getattr(b, close_attr, None) or (b.get(close_attr) if isinstance(b, dict) else None)
        v = getattr(b, volume_attr, None) or (b.get(volume_attr) if isinstance(b, dict) else 0)
        oi = getattr(b, open_interest_attr, None) or (b.get(open_interest_attr) if isinstance(b, dict) else None)
        iv = getattr(b, implied_vol_attr, None) or (b.get(implied_vol_attr) if isinstance(b, dict) else None)
        row = {"datetime": dt, "open": o, "high": h, "low": lo, "close": c, "volume": v or 0}
        if oi is not None:
            row["openinterest"] = oi
        if iv is not None:
            row["implied_vol"] = iv
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime")
    df.sort_index(inplace=True)
    return df


def dataframe_from_storage_bars(bars: Sequence[Any]) -> pd.DataFrame:
    """Build DataFrame from storage OptionsBarModel list (with optional .contract)."""
    return bars_to_dataframe(bars)


def underlying_bars_to_dataframe(bars: Sequence[Any]) -> pd.DataFrame:
    """Build DataFrame from underlying bar objects for Backtrader (e.g. PandasData)."""
    rows = []
    for b in bars:
        dt = getattr(b, "datetime", None)
        o = getattr(b, "open", None)
        h = getattr(b, "high", None)
        lo = getattr(b, "low", None)
        c = getattr(b, "close", None)
        v = getattr(b, "volume", 0)
        rows.append({"datetime": dt, "open": o, "high": h, "low": lo, "close": c, "volume": v or 0})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime")
    df.sort_index(inplace=True)
    return df
