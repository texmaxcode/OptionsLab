"""
OHLCV feature engineering for time-series forecasting.

Produces lagged returns, simple moving averages, and volatility measures
from a price/OHLCV DataFrame. Stateless and deterministic for testing.
Used by both the forecasting pipeline and (optionally) backtest analysis.
"""

import pandas as pd


def build_ohlcv_features(
    df: pd.DataFrame,
    *,
    target_col: str = "close",
    return_lags: tuple[int, ...] = (1, 2, 5),
    sma_windows: tuple[int, ...] = (5, 10, 20),
    vol_window: int = 20,
    drop_na: bool = True,
) -> pd.DataFrame:
    """
    Build a feature DataFrame from OHLCV for forecasting or analysis.

    Requires a DataFrame with datetime index and at least a "close" column
    (e.g. from features.loader.load_underlying_series or backtrader_feeds).

    Features added:
    - return: period return (close-to-close).
    - return_lag_N: lagged return for N in return_lags.
    - sma_N: simple moving average of close over N periods.
    - volatility_N: rolling std of returns over N periods (annualized scale).
    - target (optional): next-period return, for supervised learning.

    Args:
        df: DataFrame with datetime index and columns open, high, low, close, volume.
        target_col: Column to use for returns and SMAs (default "close").
        return_lags: Lag periods for return features.
        sma_windows: Windows for simple moving averages.
        vol_window: Window for rolling volatility (std of returns).
        drop_na: If True, drop rows with NaN after feature construction.

    Returns:
        New DataFrame with same index (or subset if drop_na) and feature columns.
        Original OHLCV columns are preserved.
    """
    out = df.copy()
    if target_col not in out.columns:
        raise ValueError(f"DataFrame must have column '{target_col}'")
    close = out[target_col]

    # Period return
    out["return"] = close.pct_change()

    # Lagged returns
    for lag in return_lags:
        out[f"return_lag_{lag}"] = out["return"].shift(lag)

    # Simple moving averages
    for w in sma_windows:
        out[f"sma_{w}"] = close.rolling(window=w, min_periods=1).mean()

    # Rolling volatility (annualized: std * sqrt(252) for daily)
    out["volatility"] = (
        out["return"].rolling(window=vol_window, min_periods=2).std() * (252 ** 0.5)
    )

    # Next-period return as target for supervised models (optional)
    out["target"] = out["return"].shift(-1)

    if drop_na:
        out = out.dropna()

    return out


def get_feature_columns(
    return_lags: tuple[int, ...] = (1, 2, 5),
    sma_windows: tuple[int, ...] = (5, 10, 20),
    include_target: bool = False,
) -> list[str]:
    """
    Return the list of feature column names produced by build_ohlcv_features.

    Useful for model training and API responses without duplicating parameters.
    """
    cols = ["return", "volatility"]
    for lag in return_lags:
        cols.append(f"return_lag_{lag}")
    for w in sma_windows:
        cols.append(f"sma_{w}")
    if include_target:
        cols.append("target")
    return cols
