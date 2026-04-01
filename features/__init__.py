"""
Feature engineering for time-series forecasting and backtesting.

This package produces feature DataFrames from OHLCV (and optional volatility) data.
The same data sources used by the backtesting engine (storage/repositories) are
used here so forecasts and backtests are comparable.

See docs/DATA_AND_FEATURES.md for schema and usage.
"""

from features.ohlcv_features import build_ohlcv_features
from features.loader import load_underlying_series
from features.macro_features import load_macro_features, join_macro_features

__all__ = [
    "build_ohlcv_features",
    "load_underlying_series",
    "load_macro_features",
    "join_macro_features",
]
