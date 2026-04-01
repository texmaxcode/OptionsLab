"""
Base interface for time-series forecasters.

All forecasters consume a price or return series (e.g. from features.build_ohlcv_features)
and produce point forecasts plus optional uncertainty, so the strategy engine
and backtesting integration can use a uniform API.
"""

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class BaseForecaster(ABC):
    """
    Abstract forecaster: fit on history, predict next step(s).

    Subclasses implement fit and predict. The platform uses the same
    data source (storage/repositories) for both backtesting and forecasting.
    """

    @abstractmethod
    def fit(self, series: pd.Series | pd.DataFrame, **kwargs: Any) -> "BaseForecaster":
        """Fit the model on historical data. Returns self for chaining."""
        ...

    @abstractmethod
    def predict(self, horizon: int = 1, **kwargs: Any) -> pd.Series:
        """
        Predict the next horizon steps.

        Returns:
            Series with index (e.g. date or step) and point forecast values.
        """
        ...

    def predict_direction(self, horizon: int = 1, **kwargs: Any) -> str:
        """
        Predict direction for the next step: "up", "down", or "flat".

        Default implementation uses predict(horizon=1) and compares to last
        known value; subclasses may override for model-specific logic.
        """
        pred = self.predict(horizon=horizon, **kwargs)
        if pred.empty:
            return "flat"
        # Compare predicted value to last fitted value if available
        last = getattr(self, "_last_value", None)
        if last is None:
            return "flat"
        p = float(pred.iloc[-1]) if hasattr(pred.iloc[-1], "__float__") else float(pred.iloc[-1])
        if p > last:
            return "up"
        if p < last:
            return "down"
        return "flat"
