# Macro & Economic Data Integration

This project can pull **macro and economic time-series** into the same stack you use for backtests, forecasting, and strategy evaluation.

Currently supported sources:

- **FRED (Federal Reserve Bank of St. Louis)**
- **BLS (Bureau of Labor Statistics)**
- **BEA (Bureau of Economic Analysis)**

## 1. API endpoints

### `GET /economic/series`

Fetch a normalized time-series for one provider.

**Query parameters**

- `source` – one of:
  - `fred` – FRED macro database.
  - `bls` – BLS labor / CPI timeseries.
  - `bea` – BEA NIPA (GDP and national accounts).
- `series_id` – source-specific series identifier:
  - FRED – e.g. `GDP`, `CPIAUCSL`, `UNRATE`.
    - Recommended replacements for removed sources:
      - Manufacturing activity proxy: `IPMAN` (Industrial Production: Manufacturing)
      - 10Y yield: `DGS10`
      - EUR/USD: `DEXUSEU`
      - VIX: `VIXCLS`
  - BLS – e.g. `CUUR0000SA0` (CPI), `LNS14000000` (unemployment rate).
  - BEA – NIPA `TableName`, e.g. `T10101` (GDP table). BEA data is fetched and stored to the database the same as FRED and BLS data.
- `start_date` – optional `YYYY-MM-DD` (where supported).
- `end_date` – optional `YYYY-MM-DD` (where supported).

**Response shape**

```jsonc
{
  "source": "fred",
  "series_id": "GDP",
  "points": [
    { "date": "2015-01-01", "value": 18218.3 },
    { "date": "2015-04-01", "value": 18325.7 }
    // ...
  ],
  "raw": { /* optional, provider JSON payload */ }
}
```

The `points` array is always normalized to `{date: ISO string, value: number | null}` and sorted by date.

## 2. Provider-specific notes

### 2.1 FRED

- Base docs: <https://fred.stlouisfed.org/docs/api/fred/>
- Endpoint used: `/fred/series/observations`.
- Required key: **FRED API key**.
- Supports `start_date` / `end_date` as `observation_start` / `observation_end`.

### 2.2 BLS

- Base docs: <https://www.bls.gov/developers/>
- Endpoint used: `https://api.bls.gov/publicAPI/v2/timeseries/data/` (POST).
- Required key: **BLS API key**.
- `series_id` is a standard BLS timeseries (e.g. `CUUR0000SA0`).
- When `start_date` / `end_date` are not provided, the backend requests the last **10 years**.
- Only **monthly (M01–M12)** observations are kept; annual averages (e.g. `M13`) are skipped.

### 2.3 BEA

- Base docs: <https://www.bea.gov/developers>
- Endpoint used: `https://apps.bea.gov/api/data`.
- Required key: **BEA API key**.
- `series_id` is treated as `TableName` in the **NIPA** dataset (e.g. `T10101`).
- Frequency is `Q` (quarterly); each quarter is mapped to the first day of the quarter (e.g. `2023Q1` → `2023-01-01`).

## 3. Configuration (API keys)

You can configure keys **via environment variables** or **via the web Settings page**. Settings take precedence when present.

### 3.1 Environment variables

Add to `.env` (or your deployment environment):

| Variable | Description |
|----------|-------------|
| `FRED_API_KEY` | FRED API key (`fred.stlouisfed.org`). |
| `BLS_API_KEY` | BLS API key (`bls.gov/developers`). |
| `BEA_API_KEY` | BEA API key (`bea.gov/developers`). |

### 3.2 Web Settings (dashboard)

In **Dashboard → Settings → API keys**, you can enter:

- FRED API key
- BLS API key
- BEA API key

These are stored encrypted in the `users.settings_json` blob and masked on GET (shown as `••••••••` when set). For each provider, the backend resolves keys as:

1. User settings (if present and non-empty).
2. Environment variables (fallback).

### 3.3 How to obtain keys (quick guide)

- **FRED**
  - Go to `fred.stlouisfed.org` → **My Account** → **API Keys**.
  - Generate a key and copy the string.
  - Set it either as:
    - Env: `FRED_API_KEY=...`, or
    - Dashboard: paste into **FRED API key** in Settings.

- **BLS**
  - Visit `bls.gov/developers` → **Get Started** → request an API key via email form.
  - When you receive the key, set:
    - Env: `BLS_API_KEY=...`, or
    - Dashboard: **BLS API key** in Settings.

- **BEA**
  - Go to `bea.gov/developers` → sign up for an API key.
  - After registration, set:
    - Env: `BEA_API_KEY=...`, or
    - Dashboard: **BEA API key** in Settings.

-(TradingEconomics client/key and COT are no longer used by this app.)

## 4. Dashboard integration

### 4.1 Macro dashboard page

The Next.js app exposes a dedicated page at:

- **Route:** `/dashboard/economic`
- **Nav label:** “Macro & economic”

The page lets you:

- Choose a **source** (FRED, BLS, BEA).
- Enter a **series ID / code**:
  - FRED: `GDP`, `CPIAUCSL`, `UNRATE`, `IPMAN`, `DGS10`, `DEXUSEU`, `VIXCLS`, etc.
  - BLS: `CUUR0000SA0`, `LNS14000000`, etc.
  - BEA: `T10101`, etc.
- Set **From / To** dates.
- Click **“Load series”** to call `/economic/series` and render a D3 line chart (`EconomicSeriesChart`).
- Click **“Import all presets”** to batch-import the built-in preset series for **all sources** (FRED/BLS/BEA) using the current From/To date range. Each series is fetched via `/economic/series` and stored to the DB (best-effort) by the backend.

The main Overview page also includes a **“Macro & economic data”** card linking to this dashboard.

## 5. Bulk import (CLI)

To import all preset macro series via the backend API from the command line, use:

```bash
PYTHONPATH=. python3 scripts/sync_economic.py --all-presets --from 2015-01-01 --to 2024-12-31 --to-db
```

To write one CSV per series (and optionally also write to DB):

```bash
PYTHONPATH=. python3 scripts/sync_economic.py --all-presets --output-dir data/economic
PYTHONPATH=. python3 scripts/sync_economic.py --all-presets --output-dir data/economic --to-db
```

Notes:

- The script calls the running API at `TRADING_API_URL` (default: `http://localhost:8000`).
- The preset series list is embedded in the script and matches the Macro page presets.

### 4.2 How to use in trading/research

This module supports both **visualization** and **forecasting enrichment**:

- Visualize macro series alongside backtest equity curves and TSF forecasts on the Macro & Economics dashboard page.
- **Join macro features into the forecasting pipeline** — this is now implemented via `features/macro_features.py`:
  - `load_macro_features(from_date, to_date)` loads stored economic series from the DB as a wide DataFrame.
  - `join_macro_features(ohlcv_df, macro_df)` forward-fills and joins monthly/quarterly macro readings onto daily OHLCV features.
  - Pass `include_macro: true` to `POST /forecast/run` to automatically enrich the model's training features with stored macro series.
- The RAG knowledge base in `research_assistant/rag.py` includes built-in financial context chunks about GDP, CPI, VIX, unemployment, and treasury yields, which are injected into LLM prompts when OpenAI is configured.


