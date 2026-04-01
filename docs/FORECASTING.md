# Time-Series Forecasting

This document describes the forecasting module used for the TSF Options AI platform. Forecasts use the **same market data** as the backtesting engine so that strategy evaluation and backtest results are comparable.

## Overview

- **Package:** `forecasting/`
- **Models:** ARIMA (statsmodels) and **GB** (scikit-learn `HistGradientBoostingRegressor` with lagged features). API accepts `model: "arima"` or `model: "gb"`.
- **Model registry:** Successful forecast runs are recorded in a JSON registry (configurable via `TRADING_FORECAST_REGISTRY`). **GET /forecast/runs** lists runs; optional filters: symbol, model_type, limit.
- **Evaluation:** Directional accuracy, RMSE, MAE, and simple backtest returns from forecast signals.
- **Macro enrichment:** Pass `include_macro: true` in the forecast request to join stored economic series (GDP, CPI, etc.) onto OHLCV features before fitting. Requires macro data to be synced first via the economic data routes.

## Data flow

1. **Load series:** `features.load_underlying_series(symbol, from_date, to_date)` loads OHLCV from storage (same as backtests).
2. **Features:** `features.build_ohlcv_features(df)` adds returns, lags, SMAs, volatility.
3. **Macro enrichment (optional):** `features.load_macro_features(from_date, to_date)` loads stored economic series. `features.join_macro_features(feat, macro_df)` forward-fills and joins them onto the OHLCV features.
4. **Fit:** Forecaster (e.g. `ARIMAForecaster`) is fit on the `close` column.
5. **Predict:** `predict(horizon=1)` returns point forecast; `predict_direction()` returns "up"/"down"/"flat".
6. **Evaluate:** `evaluate_forecast(actual, predicted)` and `backtest_returns_from_signals(prices, signals)` for metrics.

## Forecaster interface

All forecasters implement `forecasting.base.BaseForecaster`:

- **`fit(series)`** – Fit on historical data (Series or DataFrame with `close`).
- **`predict(horizon=1)`** – Point forecast for next `horizon` steps.
- **`predict_direction(horizon=1)`** – Directional signal for strategy/backtest comparison.

## ARIMA

- **Class:** `forecasting.arima_model.ARIMAForecaster`
- **Order:** Default `(1, 0, 0)` (AR(1)). Pass `order=(p, d, q)` for custom.
- **Input:** pandas Series (e.g. close or return) or DataFrame with `close` column.
- **Optional:** `get_confidence_interval(horizon, alpha)` for prediction intervals.

## Gradient boosting (GB)

- **Class:** `forecasting.gb_model.GBForecaster`
- **Features:** Lagged close (default `n_lag=5`) to predict next value; iterative 1-step prediction for horizon > 1.
- **Input:** Same as ARIMA (Series or DataFrame with `close`). Requires at least `n_lag + 1` points.

## Macro features

`features/macro_features.py` provides two functions:

- **`load_macro_features(from_date, to_date, series_ids=None)`** – Loads all stored economic series from the database as a wide DataFrame (one column per `source_seriesid`, e.g. `fred_GDP`). Optional `series_ids` allowlist.
- **`join_macro_features(ohlcv_df, macro_df, fill_method="ffill")`** – Reindexes macro series to the OHLCV date index and forward-fills gaps (macro is typically monthly; OHLCV is daily). Adds `macro_` prefixed columns to the OHLCV DataFrame.

The forecast API route automatically uses these when `include_macro: true` is passed. The `macro_enriched` field in the response is `true` when enrichment succeeded.

## Evaluation metrics

- **`evaluate_forecast(actual, predicted)`**  
  Returns: `directional_accuracy`, `rmse`, `mae`, `n_observations`. Aligns series by index; can pass precomputed direction series.

- **`backtest_returns_from_signals(prices, signals)`**  
  Simple rule: long when signal "up", short when "down". Returns: `total_return`, `n_trades`, `win_rate`. Uses same price semantics as the backtesting engine.

## Usage example

```python
from features import load_underlying_series, build_ohlcv_features, load_macro_features, join_macro_features
from forecasting import ARIMAForecaster, evaluate_forecast, backtest_returns_from_signals

df = load_underlying_series("AAPL", from_date="2024-01-01", to_date="2024-06-30")
feat = build_ohlcv_features(df)

# Optional: enrich with macro features
macro = load_macro_features("2024-01-01", "2024-06-30")
if not macro.empty:
    feat = join_macro_features(feat, macro)

# Fit ARIMA on close
model = ARIMAForecaster(order=(1, 0, 0)).fit(feat["close"])
pred = model.predict(horizon=5)
direction = model.predict_direction(horizon=1)
```

## Integration with backtesting

- **Same data:** Use the same symbol and date range in both backtest and forecast.
- **Compare:** Run a backtest over a period, then run a forecaster on the same period (train on earlier window, evaluate on holdout). Use `backtest_returns_from_signals` with forecaster directions to get a "strategy" return from the model.
- **API:** The FastAPI router `api/routers/forecasting.py` exposes run-forecast and evaluate endpoints so the dashboard can show forecasts alongside backtest results.

## Dependencies

- **statsmodels** – ARIMA.
- **pandas**, **numpy** – Series/DataFrame and numerics.
- **scikit-learn** – Used for `GBForecaster` (`HistGradientBoostingRegressor`).

See `requirements.txt`.
