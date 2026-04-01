# Volatility Dashboard

The Volatility Dashboard gives options traders the quantitative context they need to decide *when* to enter a position — before committing to a specific strategy.

## Why volatility matters for options

Options premiums are driven primarily by **Implied Volatility (IV)**. Buying options when IV is high means paying inflated premiums; selling options when IV is low means collecting little credit. The optimal approach:

| IV environment | IVR threshold | Preferred strategies |
|----------------|---------------|----------------------|
| High IV | IVR ≥ 60 | Iron condors, credit spreads, covered calls — sell premium |
| Neutral IV | IVR 35–59 | Either direction depending on directional forecast |
| Low IV | IVR < 35 | Long straddles, debit spreads, calendars — buy cheap vol |

These thresholds drive the color-coded **Strategy Guidance** card in the UI (red dot for high, yellow for moderate, green for low).

## Metrics

### Historical Volatility (HV)

Annualized standard deviation of log returns over a rolling window of trading days.

```
HV_n = std(log(Close_t / Close_{t-1}), n days) × √252
```

Available at four lookback windows:
- **HV-10** — short-term (fast to react, noisy)
- **HV-20** — medium-term (most commonly cited)
- **HV-30** — medium-term (options pricing standard)
- **HV-60** — long-term (trending baseline)

**Data requirement**: Underlying OHLCV bars must be synced via Data & Symbols.

### Implied Volatility (IV)

The IV shown is the daily average across all stored options contracts for the underlying symbol.

**Data requirement**: Options contracts with IV must be synced (E*TRADE sync or Massive).

### IV Rank (IVR)

How today's IV compares to the past year's high/low range, expressed as 0–100.

```
IVR = (IV_now − IV_52w_low) / (IV_52w_high − IV_52w_low) × 100
```

- IVR 0 = IV is at its lowest point of the year
- IVR 100 = IV is at its highest point of the year
- IVR 50 = IV is exactly in the middle of the year's range

### IV Percentile (IVP)

The percentage of trading days in the history window where IV was *lower* than today.

```
IVP = count(IV_history < IV_now) / count(IV_history) × 100
```

- IVP 80 = today's IV is higher than 80% of past readings → expensive options
- IVP 20 = today's IV is cheaper than 80% of past readings → cheap options

**IVR vs IVP**: IVR is range-based (sensitive to outlier spikes). IVP is percentile-based (more robust). Both are useful; differences arise when there are IV spikes.

### Expected Move (1σ, 30-day)

The market's implied price range over 30 calendar days, using the Black-Scholes approximation:

```
EM = Current Price × IV × √(30 / 252)
```

This matches the shortcut: *straddle price ≈ expected move*. At 1σ, ~68% of outcomes land inside this range.

## API

```
GET /volatility/{symbol}?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD
```

**Authentication**: Bearer token required.

**Response fields**:

| Field | Type | Description |
|-------|------|-------------|
| `current_price` | float | Latest underlying close price |
| `current_iv` | float | Latest average IV across all stored contracts |
| `hv_10` | float | 10-day annualized HV (decimal, e.g. 0.25 = 25%) |
| `hv_20` | float | 20-day annualized HV |
| `hv_30` | float | 30-day annualized HV |
| `hv_60` | float | 60-day annualized HV |
| `iv_rank` | float | IVR 0–100 |
| `iv_percentile` | float | IVP 0–100 |
| `expected_move_30d_dollar` | float | 1σ expected move in $ |
| `expected_move_30d_pct` | float | 1σ expected move as % of price |
| `iv_series` | list | Daily IV data points for charting |
| `hv_20_series` | list | Daily 20-day HV data points for charting |

**Example**:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/volatility/AAPL?from_date=2024-01-01&to_date=2024-12-31"
```

## UI Layout

The Volatility Dashboard (`/dashboard/volatility`) is organized into five sections:

1. **Controls** — Symbol selector, From/To date pickers, and the Analyze button. Defaults are pre-filled from user Settings.

2. **Current Levels** — Five metric cards side by side:
   - Current Price, Current IV, IV Rank (with progress bar gauge), IV Percentile, Expected Move (30d).
   - The IV Rank card uses a filled progress bar (0–100) and color-codes the border: red for high (≥ 60), yellow for moderate (≥ 35), green for low.

3. **Historical Volatility** — Four metric cards: HV-10, HV-20, HV-30, HV-60 (all annualized, in a 2×2 grid on mobile, 4-column on desktop). Each shows the lookback window as a subtitle.

4. **Strategy Guidance** — A text card that appears once IV Rank is known. Color-coded dot (red/yellow/green) and a short actionable summary recommending premium-selling or premium-buying strategies.

5. **IV vs HV-20 Chart** — An `svg`-based D3 time-series chart (`VolatilityChart`) overlaying IV (orange) and HV-20 (green) over the selected date range. When IV data is unavailable, an empty-state card is shown instead.

## Code location

| Component | Path |
|-----------|------|
| Core metrics | `volatility/metrics.py` |
| Module exports | `volatility/__init__.py` |
| API router | `api/routers/volatility.py` |
| Frontend page | `web/app/dashboard/volatility/page.tsx` |
| Chart component | `web/components/VolatilityChart.tsx` |
| Frontend API client | `web/lib/volatilityApi.ts` |

## Data requirements

The dashboard works in two modes depending on what has been synced for the selected symbol:

**Underlying OHLCV bars only** (minimum requirement):
- All four HV windows (HV-10/20/30/60) are computed and displayed.
- IV Rank, IV Percentile, Expected Move, and the IV vs HV chart cannot be shown.
- Seed demo data with `scripts/seed_dummy_data.py` to test this mode without API keys.

**Underlying bars + options contracts with implied volatility**:
- All HV windows are shown.
- IV Rank, IV Percentile, and Expected Move are computed and shown.
- Strategy Guidance card appears with a color-coded recommendation.
- The IV vs HV-20 time-series chart is rendered.
- Sync options data via `--source massive` or E*TRADE (with IV populated in `options_bars.implied_volatility`).
