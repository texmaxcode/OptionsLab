"""
Time-series forecasting for options and equity research.

Provides baseline (ARIMA) and evaluation metrics (directional accuracy, RMSE,
backtest returns). Forecasts use the same market data as the backtesting
engine so results are comparable.

See docs/FORECASTING.md for usage and integration with the platform.
"""

from forecasting.arima_model import ARIMAForecaster
from forecasting.gb_model import GBForecaster
from forecasting.evaluation import evaluate_forecast, backtest_returns_from_signals

__all__ = [
    "ARIMAForecaster",
    "GBForecaster",
    "evaluate_forecast",
    "backtest_returns_from_signals",
]
