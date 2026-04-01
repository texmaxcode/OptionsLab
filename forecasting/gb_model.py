"""
Gradient boosting forecaster for price series.

Uses scikit-learn HistGradientBoostingRegressor with lagged features.
Same I/O contract as ARIMAForecaster: fit on history, predict horizon steps,
directional signal. Use for regression (next-day price or return).
"""

from typing import Any

import numpy as np
import pandas as pd

from forecasting.base import BaseForecaster


def _extract_close(series: pd.Series | pd.DataFrame) -> pd.Series:
    """Extract close series from DataFrame or Series."""
    if isinstance(series, pd.DataFrame):
        if "close" in series.columns:
            return series["close"].astype(float)
        return series.iloc[:, 0].astype(float)
    return series.astype(float)


def _build_lag_features(s: pd.Series, n_lag: int) -> tuple[np.ndarray, np.ndarray]:
    """Build X (lagged values) and y (next value). Drops NaNs."""
    s = s.dropna()
    if len(s) < n_lag + 1:
        return np.array([]).reshape(0, n_lag), np.array([])
    vals = s.values
    X = np.column_stack([vals[i : -(n_lag - i)] for i in range(n_lag)])
    y = vals[n_lag:]
    return X, y


class GBForecaster(BaseForecaster):
    """
    Gradient boosting forecaster using lagged close (or return) as features.

    Fit on a pandas Series or DataFrame with 'close'; predict next horizon steps
    via iterative 1-step prediction. Same interface as ARIMAForecaster.
    """

    def __init__(
        self,
        n_lag: int = 5,
        **kwargs: Any,
    ) -> None:
        """
        Args:
            n_lag: Number of lagged values used as features.
            **kwargs: Passed to HistGradientBoostingRegressor (e.g. max_iter, learning_rate).
        """
        self.n_lag = n_lag
        self._kwargs = kwargs
        self._model = None
        self._series: pd.Series | None = None
        self._last_value: float | None = None
        self._last_lags: np.ndarray | None = None

    def fit(self, series: pd.Series | pd.DataFrame, **kwargs: Any) -> "GBForecaster":
        """Fit gradient boosting on lagged features from the given series."""
        from sklearn.ensemble import HistGradientBoostingRegressor

        s = _extract_close(series).dropna()
        if s.empty or len(s) < self.n_lag + 1:
            raise ValueError(
                f"Series must have at least {self.n_lag + 1} non-NaN points to fit GBForecaster"
            )
        self._series = s
        self._last_value = float(s.iloc[-1])
        X, y = _build_lag_features(s, self.n_lag)
        self._model = HistGradientBoostingRegressor(**self._kwargs)
        self._model.fit(X, y)
        self._last_lags = X[-1].copy()
        return self

    def predict(self, horizon: int = 1, **kwargs: Any) -> pd.Series:
        """Forecast the next horizon steps. Returns a Series with integer index 0..horizon-1."""
        if self._model is None or self._last_lags is None:
            raise RuntimeError("Call fit() before predict()")
        preds: list[float] = []
        lags = self._last_lags.copy()
        for _ in range(horizon):
            next_val = float(self._model.predict(lags.reshape(1, -1))[0])
            preds.append(next_val)
            lags = np.roll(lags, -1)
            lags[-1] = next_val
        return pd.Series(preds, index=range(horizon))

    def predict_direction(self, horizon: int = 1, **kwargs: Any) -> str:
        """Direction based on predicted value vs last observed."""
        if self._last_value is None:
            return "flat"
        pred = self.predict(horizon=horizon, **kwargs)
        if pred.empty:
            return "flat"
        p = float(pred.iloc[-1])
        if p > self._last_value:
            return "up"
        if p < self._last_value:
            return "down"
        return "flat"
