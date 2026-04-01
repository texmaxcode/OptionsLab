# Data and Feature Engineering

This document describes the market data and feature pipeline used by both **backtesting** and **time-series forecasting** so that results are comparable and share the same data foundation.

## Data sources

- **Underlying OHLCV:** Stored in `underlying_bars` (see `models.sql_models.UnderlyingBarModel`). Ingested via `data/sync.py` (Massive) or `data/etrade_sync.py` (E*TRADE).
- **Options chains and bars:** Stored in `options_contracts` and `options_bars`. Options bars may include `implied_volatility` and Greeks when provided by the data source.

Both the backtesting engine (`api/services/run_backtest.py`, `strategies/`, `backtrader_feeds/`) and the forecasting pipeline (`features/`, `forecasting/`) read from these same tables.

## Feature pipeline (`features/`)

### Loading data

- **`features.loader.load_underlying_series(symbol, from_date, to_date)`**  
  Loads underlying OHLCV from storage into a pandas DataFrame with datetime index and columns: `open`, `high`, `low`, `close`, `volume`. Uses `UnderlyingBarRepository` and `backtrader_feeds.underlying_bars_to_dataframe`, so the series is identical to what backtests use.

### Building features

- **`features.ohlcv_features.build_ohlcv_features(df, ...)`**  
  Takes an OHLCV DataFrame (e.g. from `load_underlying_series`) and adds:
  - **return:** Close-to-close period return.
  - **return_lag_N:** Lagged return for configurable lags (default 1, 2, 5).
  - **sma_N:** Simple moving average of close over N periods (default 5, 10, 20).
  - **volatility:** Rolling standard deviation of returns (default 20-period), annualized.
  - **target:** Next-period return (for supervised forecasting).

Parameters: `target_col`, `return_lags`, `sma_windows`, `vol_window`, `drop_na`. See docstrings in `features/ohlcv_features.py`.

### Feature column names

- **`features.ohlcv_features.get_feature_columns(...)`**  
  Returns the list of feature column names for a given configuration, so training and API code stay in sync.

### Macro feature enrichment

- **`features.macro_features.load_macro_features(from_date, to_date, series_ids=None)`**  
  Loads stored economic series from the database as a wide DataFrame (one column per `source_seriesid`, e.g. `fred_GDP`, `fred_CPIAUCSL`). Requires macro data to be synced first via the economic data routes or the `sync_economic.py` script.

- **`features.macro_features.join_macro_features(ohlcv_df, macro_df, fill_method="ffill", prefix="macro_")`**  
  Reindexes macro series (typically monthly/quarterly) to the OHLCV date index and forward-fills gaps, then joins as additional columns (e.g. `macro_fred_GDP`). Returns the enriched DataFrame.

The forecast API route accepts `include_macro: true` to automatically load and join macro features before model fitting. The response includes `macro_enriched: true` when enrichment succeeded.

## Integration with backtesting

- Backtests get bars via `UnderlyingBarRepository.get_bars()` and convert to DataFrame with `underlying_bars_to_dataframe()`.
- Forecasting loads the same symbol/date range with `load_underlying_series()` (which uses the same repository and converter).
- No duplicate storage: one source of truth in the database.

## Volatility

- **Underlying:** Rolling volatility of returns is computed in the feature pipeline (`volatility`).
- **Options:** When available, `options_bars.implied_volatility` is stored and can be used for strategy evaluation and as context for the Research Assistant (RAG/LLM explanations).

## Usage example

```python
from features import load_underlying_series, build_ohlcv_features, load_macro_features, join_macro_features

df = load_underlying_series("AAPL", from_date="2024-01-01", to_date="2024-06-30")
features_df = build_ohlcv_features(df, return_lags=(1, 5), sma_windows=(10, 20))

# Optional: enrich with macro series (requires data to be synced via economic routes)
macro = load_macro_features("2024-01-01", "2024-06-30")
if not macro.empty:
    features_df = join_macro_features(features_df, macro)

# Use features_df for forecasting or analysis; same data as backtests for same range
```
