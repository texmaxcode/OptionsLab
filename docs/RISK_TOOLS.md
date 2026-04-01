# Risk Tools

Risk management features: position sizing (Kelly Criterion), break-even analysis, and standard risk metrics (max drawdown, VaR).

## Position Sizing

**Location in UI**: Research & AI page → **Position Sizing** card (bottom of page)

Enter capital, historical win rate, average win/loss amounts, and maximum risk percentage. Click **Calculate**. Results appear as four metric cards:
- **Full Kelly %** — fraction of capital to risk per trade at full Kelly (usually too aggressive).
- **Half Kelly % ✓** — recommended. Cuts variance dramatically while preserving ~75% of optimal growth.
- **Fixed Risk (X%)** — dollar amount at risk based on the max risk percentage you entered.
- **Max Contracts** — maximum number of contracts given the fixed risk budget and max loss per contract.

### The Kelly Criterion

The Kelly Criterion computes the *optimal fraction of capital* to risk on a trade to maximize long-run growth rate, given a known edge.

```
f* = (p × b − q) / b

where:
  p = win rate (e.g. 0.55)
  q = loss rate = 1 − p
  b = avg_win / avg_loss  (the "odds ratio")
```

**Example**: Win rate 55%, avg win $500, avg loss $300
- b = 500 / 300 = 1.667
- f* = (0.55 × 1.667 − 0.45) / 1.667 = 0.917 / 1.667 ≈ 0.55 → 55% of capital

In practice, 55% would be very aggressive and would lead to enormous drawdowns. Most practitioners use:

### Half-Kelly (recommended)

```
f_half = f* / 2
```

Half-Kelly retains ~75% of the long-run growth rate of full Kelly while dramatically reducing drawdowns. It also provides a safety margin for estimation error in the win rate and average win/loss.

**Recommended**: Use half-Kelly or less as your maximum risk per trade.

### Fixed Fractional (Fixed Risk %)

Regardless of Kelly, many traders use a simple rule: risk at most X% of capital on any single trade.

```
Units = (Capital × risk_pct) / loss_per_unit
```

The "loss per unit" for an options spread is typically the net debit paid × contract multiplier.

### Max Contracts

Given a fixed risk budget and a known maximum loss per contract:

```
Max contracts = ⌊(Capital × max_risk_pct) / (max_loss_per_contract × multiplier)⌋
```

**Example**: $10,000 capital, 1% max risk, $2.00 debit spread, 100-share multiplier
- Risk budget = $10,000 × 0.01 = $100
- Cost per contract = $2.00 × 100 = $200
- Max contracts = ⌊$100 / $200⌋ = 0 → this position is too expensive for 1% risk

## Break-Even Analysis

**Location in UI**: Research & AI page → **Evaluate strategy** card → **Premium paid ($)** field

Enter the net debit paid (positive) or credit received (negative) in the "Premium paid ($)" field alongside the strategy parameters. After clicking **Evaluate strategy**, the results section shows:
- A 2×2 metric grid: Expected Value, P(profit), Max Loss (red), Max Gain (green).
- **Break-even at expiry** — one or two highlighted amber badges showing the underlying prices where the strategy nets zero.
- The payoff diagram chart.

Break-even is the underlying price at expiry where a strategy's net P&L equals zero.

### Formulas by strategy

| Strategy | Break-even formula |
|----------|--------------------|
| Long Straddle | Strike ± Premium paid |
| Bull Call Spread | Long strike + Net debit |
| Bear Put Spread | Long strike − Net debit |
| Iron Condor | Put short − Net credit; Call short + Net credit |
| Calendar Spread | Strike ± (Net debit / 2) — approximation |

**Usage**: Enter the premium paid (or credit received as a negative number) in the "Premium paid ($)" field when evaluating a strategy. Break-even prices appear below the metrics.

## API

### POST /risk/position-size

Calculate optimal position size.

**Request**:
```json
{
  "capital": 10000,
  "win_rate": 0.55,
  "avg_win": 500,
  "avg_loss": 300,
  "max_risk_pct": 1.0,
  "max_loss_per_contract": 2.0,
  "contract_multiplier": 100
}
```

**Response**:
```json
{
  "success": true,
  "kelly_fraction": 0.55,
  "half_kelly_fraction": 0.275,
  "kelly_dollar_risk": 5500,
  "half_kelly_dollar_risk": 2750,
  "fixed_risk_dollar": 100,
  "fixed_risk_units": 50,
  "max_contracts": 0
}
```

### POST /risk/breakeven

Compute break-even prices for a strategy.

**Request**:
```json
{
  "strategy_type": "straddle",
  "strike": 100,
  "premium_paid": 5.0
}
```

**Response**:
```json
{
  "success": true,
  "strategy_type": "straddle",
  "breakeven_prices": [95.0, 105.0],
  "premium_paid": 5.0
}
```

### POST /strategy-engine/evaluate (extended)

The strategy evaluation endpoint now accepts an optional `premium_paid` field and returns `breakeven_prices`.

```json
{
  "strategy_type": "straddle",
  "forecast_mean": 100,
  "forecast_std": 5,
  "strike": 100,
  "premium_paid": 3.50
}
```

Response includes:
```json
{
  "breakeven_prices": [96.5, 103.5]
}
```

## Standard Risk Metrics

These are used internally by the backtest engine and strategy evaluation:

| Metric | Function | Description |
|--------|----------|-------------|
| Max Drawdown | `risk.max_drawdown(curve)` | Largest peak-to-trough decline as a fraction |
| Annualized Volatility | `risk.volatility_annualized(returns)` | Std of daily returns × √252 |
| Historical VaR (95%) | `risk.var_historical(returns, 0.95)` | 5th percentile loss level |

## Code location

| Component | Path |
|-----------|------|
| Position sizing | `risk/position_sizing.py` |
| Risk metrics | `risk/metrics.py` |
| Module exports | `risk/__init__.py` |
| API router | `api/routers/risk.py` |
| Break-even module | `strategy_engine/breakeven.py` |
| Frontend API client | `web/lib/riskApi.ts` |
| Research page (UI) | `web/app/dashboard/research/page.tsx` |
