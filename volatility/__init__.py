"""
Volatility analytics: Historical Volatility, IV Rank, IV Percentile, Expected Move.

These functions are used by the Volatility Dashboard API to help traders
time strategy selection — high IV favors premium selling, low IV favors buying.
"""

from volatility.metrics import (
    historical_volatility,
    iv_rank,
    iv_percentile,
    expected_move,
    hv_series,
)

__all__ = [
    "historical_volatility",
    "iv_rank",
    "iv_percentile",
    "expected_move",
    "hv_series",
]
