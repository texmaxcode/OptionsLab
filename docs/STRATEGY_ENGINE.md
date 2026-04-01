# Strategy Engine (Forecast-Based Options Evaluation)

The strategy engine evaluates options strategies using a **forecast distribution** of the underlying price (from the TSF module), not only historical backtests. Existing Backtrader backtests remain the source of historical performance; this engine is for forward-looking evaluation.

## Strategy types

- **vertical_spread_call** – Bull call spread: long call at `long_strike`, short call at `short_strike` (long_strike < short_strike).
- **vertical_spread_put** – Bear put spread: long put at `long_strike`, short put at `short_strike` (long_strike > short_strike).
- **straddle** – Long call + long put at the same `strike`.
- **iron_condor** – Short put spread + short call spread: `put_long`, `put_short`, `call_short`, `call_long` (put_long < put_short < call_short < call_long).
- **calendar_spread_call** / **calendar_spread_put** – Simplified calendar (long back-month, short front-month, same strike). Params: `strike`, `net_debit` (cost of spread).

All payoffs are European-style (at expiry). Per-share payoffs.

## Inputs

- **Forecast distribution:** Either a point forecast (mean) and optional standard deviation, or a discrete list of (price, probability). The engine builds a distribution via `distribution_from_forecast(mean, std)` when only mean/std are given.
- **Strategy parameters:** Strikes (and for iron condor, all four strikes). Passed in the API request or derived from forecast mean for defaults.

## Outputs

- **expected_value** – Expected payoff under the forecast distribution.
- **probability_of_profit** – Probability that payoff > 0.
- **max_loss** / **max_gain** – Worst and best payoff in the diagram range.
- **payoff_diagram** – List of `{underlying, payoff}` points for UI charts.
- **breakeven_prices** – List of break-even underlying prices at expiry (populated when `premium_paid` is provided).

## Break-Even Analysis

When `premium_paid` is included in the evaluate request, the response includes `breakeven_prices` — the underlying price(s) at expiry where the strategy's net P&L equals zero.

| Strategy | Formula | Example |
|----------|---------|---------|
| Straddle | Strike ± premium | Strike 100, premium $4 → BE at $96 and $104 |
| Bull Call Spread | Long strike + net debit | Long $98, debit $2 → BE at $100 |
| Bear Put Spread | Long strike − net debit | Long $102, debit $2 → BE at $100 |
| Iron Condor | Put short − credit; Call short + credit | PS $97, CS $103, credit $1.50 → BE at $95.50 and $104.50 |
| Calendar | Strike ± (net_debit / 2) | Strike $100, debit $2 → BE at ~$99 and ~$101 (approximation) |

The UI displays break-even prices as highlighted badges in the strategy result section.

## API

- **POST /strategy-engine/evaluate** – Body: `strategy_type`, `forecast_mean`, `forecast_std` (optional), strategy params, and optionally `premium_paid` (net debit paid; positive = debit, negative = credit for iron condors). Optional: `symbol`, `from_date`, `to_date`, `include_backtest=true` to attach a historical equity backtest comparison. Response then includes `breakeven_prices`, `historical_backtest_return`, `historical_backtest_drawdown`, and `historical_backtest_error` when applicable.

- **POST /strategy-engine/discover** – Automated strategy discovery. Provide `symbol`, `from_date`, `to_date`, `horizon`, `model` (arima or gb), and optional `spread_width_pct` (default 2%). The endpoint runs a forecast automatically, evaluates all six strategy types with auto-generated parameters, and returns them ranked by expected value descending. Useful for quickly finding the highest-EV strategy for a given symbol and period without specifying individual parameters.

  Example request:
  ```json
  {
    "symbol": "AAPL",
    "from_date": "2024-01-01",
    "to_date": "2024-06-30",
    "horizon": 5,
    "model": "arima",
    "spread_width_pct": 0.02
  }
  ```
  Response includes `forecast_direction`, `forecast_mean`, `forecast_std`, and a `results` list with `rank`, `strategy_type`, `expected_value`, `probability_of_profit`, `max_loss`, `max_gain`, and auto-generated `params`.

## Integration with backtesting

- Backtests (`strategies/`, `api/services/run_backtest.py`) use historical data and produce equity curves and trades.
- The strategy engine uses the **same** data source (forecast from the same symbol/range) to produce expected payoff. You can compare "historical backtest return" with "forecast-based expected value" for the same strategy name where applicable.

## Package layout

- `strategy_engine/payoff.py` – Payoff-at-expiry functions.
- `strategy_engine/strategies.py` – StrategyKind enum and payoff dispatch.
- `strategy_engine/expected_value.py` – Expected payoff, risk, and diagram from a distribution.
- `strategy_engine/breakeven.py` – Break-even price computation for all strategy types.

## Related documentation

- **`docs/VOLATILITY.md`** – IV Rank and HV metrics for timing strategy entry.
- **`docs/RISK_TOOLS.md`** – Position sizing (Kelly), break-even API, and risk metrics.
