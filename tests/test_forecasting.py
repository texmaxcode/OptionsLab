"""Tests for the forecasting module."""

import pandas as pd
import pytest

from forecasting import (
    ARIMAForecaster,
    GBForecaster,
    backtest_returns_from_signals,
    evaluate_forecast,
)


def test_arima_forecaster_fit_predict() -> None:
    s = pd.Series([100.0, 101.0, 99.0, 102.0, 100.5, 103.0] * 5)
    model = ARIMAForecaster(order=(1, 0, 0)).fit(s)
    pred = model.predict(horizon=2)
    assert len(pred) == 2
    assert pred.notna().all()
    direction = model.predict_direction(horizon=1)
    assert direction in ("up", "down", "flat")


def test_arima_forecaster_fit_dataframe_with_close() -> None:
    df = pd.DataFrame({"close": [100.0 + i * 0.5 for i in range(20)]})
    model = ARIMAForecaster(order=(1, 0, 0)).fit(df)
    pred = model.predict(horizon=1)
    assert len(pred) == 1


def test_arima_forecaster_predict_before_fit_raises() -> None:
    model = ARIMAForecaster()
    with pytest.raises(RuntimeError, match="fit"):
        model.predict(horizon=1)


def test_arima_forecaster_fit_short_series_raises() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        ARIMAForecaster().fit(pd.Series([1.0]))


def test_evaluate_forecast() -> None:
    actual = pd.Series([1.0, 2.0, 1.5, 3.0], index=range(4))
    predicted = pd.Series([1.1, 1.9, 1.6, 2.8], index=range(4))
    metrics = evaluate_forecast(actual, predicted)
    assert "directional_accuracy" in metrics
    assert "rmse" in metrics
    assert "mae" in metrics
    assert "n_observations" in metrics
    assert 0 <= metrics["directional_accuracy"] <= 1
    assert metrics["n_observations"] == 4


def test_evaluate_forecast_empty_returns_zeros() -> None:
    actual = pd.Series([1.0, 2.0])
    predicted = pd.Series(index=[10, 11])  # no index overlap
    metrics = evaluate_forecast(actual, predicted)
    assert metrics["n_observations"] == 0
    assert metrics["directional_accuracy"] == 0.0
    assert metrics["rmse"] == 0.0


def test_backtest_returns_from_signals() -> None:
    prices = pd.Series([100.0, 102.0, 101.0, 105.0], index=range(4))
    signals = pd.Series(["flat", "up", "down", "up"], index=range(4))
    result = backtest_returns_from_signals(prices, signals)
    assert "total_return" in result
    assert "n_trades" in result
    assert "win_rate" in result
    assert 0 <= result["win_rate"] <= 1


def test_gb_forecaster_fit_predict() -> None:
    s = pd.Series([100.0, 101.0, 99.0, 102.0, 100.5, 103.0, 101.0, 102.5, 104.0, 103.5])
    model = GBForecaster(n_lag=3).fit(s)
    pred = model.predict(horizon=2)
    assert len(pred) == 2
    assert pred.notna().all()
    direction = model.predict_direction(horizon=1)
    assert direction in ("up", "down", "flat")


def test_gb_forecaster_fit_short_series_raises() -> None:
    with pytest.raises(ValueError, match="at least"):
        GBForecaster(n_lag=5).fit(pd.Series([1.0, 2.0, 3.0]))


def test_gb_forecaster_predict_before_fit_raises() -> None:
    model = GBForecaster()
    with pytest.raises(RuntimeError, match="fit"):
        model.predict(horizon=1)
