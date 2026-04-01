"""
ARIMA baseline forecaster for price or return series.

Uses statsmodels. Fit on historical close (or returns); predict next step(s).
Integrates with the same data pipeline as backtesting (features.loader, features.ohlcv_features).
"""

from typing import Any

import pandas as pd

from forecasting.base import BaseForecaster


class ARIMAForecaster(BaseForecaster):
    """
    ARIMA(p,d,q) forecaster for a univariate series (e.g. close price or return).

    Fit on a pandas Series with datetime index; predict next horizon steps.
    """

    def __init__(self, order: tuple[int, int, int] = (1, 0, 0), **kwargs: Any) -> None:
        """
        Args:
            order: (p, d, q) for ARIMA. Default (1, 0, 0) is AR(1).
            **kwargs: Passed to statsmodels ARIMA (e.g. seasonal_order).
        """
        self.order = order
        self._kwargs = kwargs
        self._model = None
        self._fitted_result = None
        self._series: pd.Series | None = None
        self._last_value: float | None = None

    def fit(self, series: pd.Series | pd.DataFrame, **kwargs: Any) -> "ARIMAForecaster":
        """Fit ARIMA on the given series. If DataFrame, uses the first column or 'close'."""
        from statsmodels.tsa.arima.model import ARIMA

        if isinstance(series, pd.DataFrame):
            if "close" in series.columns:
                s = series["close"].astype(float)
            else:
                s = series.iloc[:, 0].astype(float)
        else:
            s = series.astype(float)
        s = s.dropna()
        # Ensure a clean, monotonic DatetimeIndex (statsmodels/pandas can be picky).
        if isinstance(s.index, pd.DatetimeIndex):
            if not s.index.is_monotonic_increasing:
                s = s.sort_index()
            # If there are duplicate timestamps, keep the last observation.
            if not s.index.is_unique:
                s = s[~s.index.duplicated(keep="last")]
        if s.empty or len(s) < 2:
            raise ValueError("Series must have at least 2 non-NaN points to fit ARIMA")
        # Set explicit frequency only if it can be inferred.
        # Do NOT force a daily freq on irregular indices (it can raise:
        # "Inferred frequency None from passed values does not conform to passed frequency D").
        if isinstance(s.index, pd.DatetimeIndex) and getattr(s.index, "freq", None) is None:
            inferred = pd.infer_freq(s.index)
            if inferred is not None:
                s = s.copy()
                s.index.freq = inferred
            else:
                # Statsmodels will ignore a DatetimeIndex without freq and may raise in future versions.
                # Use an explicit integer index since this model forecasts "next N steps" only.
                s = pd.Series(s.to_numpy(copy=False), index=pd.RangeIndex(len(s)), name=s.name)
        self._series = s
        self._last_value = float(s.iloc[-1])
        self._model = ARIMA(s, order=self.order, **self._kwargs)
        self._fitted_result = self._model.fit()
        return self

    def predict(self, horizon: int = 1, **kwargs: Any) -> pd.Series:
        """Forecast the next horizon steps. Returns a Series with integer index 0..horizon-1."""
        if self._fitted_result is None:
            raise RuntimeError("Call fit() before predict()")
        f = self._fitted_result.get_forecast(steps=horizon)
        pred = f.predicted_mean
        pred.index = range(horizon)
        return pred

    def predict_direction(self, horizon: int = 1, **kwargs: Any) -> str:
        """Direction based on predicted value vs last observed (for returns or price)."""
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

    def get_confidence_interval(self, horizon: int = 1, alpha: float = 0.05) -> pd.DataFrame:
        """Return forecast with lower and upper confidence bounds (if supported)."""
        if self._fitted_result is None:
            raise RuntimeError("Call fit() before get_confidence_interval()")
        f = self._fitted_result.get_forecast(steps=horizon)
        return f.summary_frame(alpha=alpha)
