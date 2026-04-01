"""
Volatility metrics for options strategy timing.

Key concepts
------------
Historical Volatility (HV):
    Annualized standard deviation of log returns, computed over a rolling window
    of trading days (typically 10, 20, 30, or 60 days). Measures realized price
    movement — it tells you how much the stock HAS moved.

Implied Volatility (IV):
    Volatility implied by current options prices.  Higher IV means the market
    is pricing in larger future moves.  Lower IV means the market is complacent.

IV Rank (IVR):
    Where today's IV sits within the 52-week high/low range (0–100).
    IVR = (IV_now - IV_52w_low) / (IV_52w_high - IV_52w_low) × 100.
    IVR > 50 → relatively high IV; IVR < 30 → relatively low IV.

IV Percentile (IVP):
    Percentage of trading days in the past year where IV was LOWER than today.
    IVP 80 means IV is in the top 20 % of the year — historically expensive.

Expected Move:
    The market's 1-sigma expected price range for a period:
        EM = Price × IV × sqrt(DTE / 252)
    At 1σ: ~68 % of occurrences land inside.  At 2σ: ~95 %.

Strategy guidance (rule of thumb):
    IVR / IVP > 50–60  →  sell premium (iron condors, covered calls, credit spreads)
    IVR / IVP < 30–40  →  buy premium (straddles, debit spreads, calendars)
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR: int = 252


def historical_volatility(closes: pd.Series, window: int) -> float | None:
    """
    Annualized close-to-close historical volatility over *window* trading days.

    Returns None when there are fewer than ``window + 1`` data points or when
    the rolling window produces NaN (e.g. constant price).

    Args:
        closes: pandas Series of closing prices, sorted oldest-first.
        window: Number of trading days to use (e.g. 10, 20, 30, 60).

    Returns:
        Annualized HV as a decimal (e.g. 0.25 = 25 %) or None.
    """
    if len(closes) < window + 1:
        return None
    log_ret = np.log(closes / closes.shift(1)).dropna()
    rolling_std = log_ret.rolling(window).std()
    val = rolling_std.iloc[-1]
    if pd.isna(val):
        return None
    return float(val * math.sqrt(TRADING_DAYS_PER_YEAR))


def hv_series(closes: pd.Series, window: int) -> pd.Series:
    """
    Rolling annualized HV series for the full history.

    Returns a Series with the same index as *closes*, NaN where insufficient data.
    """
    log_ret = np.log(closes / closes.shift(1)).dropna()
    return log_ret.rolling(window).std() * math.sqrt(TRADING_DAYS_PER_YEAR)


def iv_rank(current_iv: float, iv_history: pd.Series) -> float | None:
    """
    IV Rank (IVR): 0–100 score indicating where current IV sits within 52-week range.

    IVR = (IV_now − IV_52w_low) / (IV_52w_high − IV_52w_low) × 100

    Args:
        current_iv: Today's IV (decimal, e.g. 0.30 for 30 %).
        iv_history: Series of daily IV values covering (at least) the past year.

    Returns:
        IVR as a float in [0, 100], or None if history is empty.
    """
    clean = iv_history.dropna()
    if clean.empty:
        return None
    low, high = float(clean.min()), float(clean.max())
    if math.isclose(high, low):
        return 50.0
    return round((current_iv - low) / (high - low) * 100.0, 1)


def iv_percentile(current_iv: float, iv_history: pd.Series) -> float | None:
    """
    IV Percentile (IVP): fraction of days in history where IV was below current level.

    E.g. IVP = 80 means IV is higher than 80 % of past readings — expensive options.

    Args:
        current_iv: Today's IV (decimal).
        iv_history: Series of daily IV values covering (at least) the past year.

    Returns:
        IVP in [0, 100] or None if history is empty.
    """
    clean = iv_history.dropna()
    if clean.empty:
        return None
    below = int((clean < current_iv).sum())
    return round(below / len(clean) * 100.0, 1)


def expected_move(current_price: float, iv: float, dte: int) -> float:
    """
    One-sigma expected move for a given period.

    Formula: Price × IV × sqrt(DTE / 252)

    This matches the simplified "straddle price ≈ expected move" shortcut
    used by market makers.

    Args:
        current_price: Current underlying price.
        iv: Implied volatility (decimal, e.g. 0.30).
        dte: Days to expiration (calendar days; use DTE / 252 for trading day ratio).

    Returns:
        Dollar expected move (1σ).
    """
    return current_price * iv * math.sqrt(dte / TRADING_DAYS_PER_YEAR)
