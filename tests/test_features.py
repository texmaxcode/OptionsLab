"""Tests for the feature engineering pipeline."""

import pandas as pd
import pytest

from features.ohlcv_features import build_ohlcv_features, get_feature_columns


def test_build_ohlcv_features_requires_close() -> None:
    df = pd.DataFrame({"open": [1.0], "high": [2.0], "low": [0.5]})
    with pytest.raises(ValueError, match="close"):
        build_ohlcv_features(df)


def test_build_ohlcv_features_produces_expected_columns() -> None:
    dates = pd.date_range("2024-01-01", periods=50, freq="D")
    df = pd.DataFrame(
        {
            "open": 100.0 + pd.Series(range(50)).astype(float),
            "high": 101.0 + pd.Series(range(50)).astype(float),
            "low": 99.0 + pd.Series(range(50)).astype(float),
            "close": 100.0 + pd.Series(range(50)).astype(float),
            "volume": [1000] * 50,
        },
        index=dates,
    )
    out = build_ohlcv_features(df, return_lags=(1, 2), sma_windows=(5,), vol_window=10)
    assert "return" in out.columns
    assert "return_lag_1" in out.columns
    assert "return_lag_2" in out.columns
    assert "sma_5" in out.columns
    assert "volatility" in out.columns
    assert "target" in out.columns
    if out.shape[0] > 0:
        assert out["return"].notna().any() or out["return"].isna().all()


def test_build_ohlcv_features_drop_na() -> None:
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    df = pd.DataFrame(
        {"close": [100.0 + i for i in range(30)], "volume": [1000] * 30},
        index=dates,
    )
    out = build_ohlcv_features(df, drop_na=True)
    assert out.isna().sum().sum() == 0


def test_get_feature_columns() -> None:
    cols = get_feature_columns(return_lags=(1, 5), sma_windows=(10,), include_target=True)
    assert "return" in cols
    assert "return_lag_1" in cols
    assert "return_lag_5" in cols
    assert "sma_10" in cols
    assert "volatility" in cols
    assert "target" in cols
