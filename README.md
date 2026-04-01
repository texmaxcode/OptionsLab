# Options Backtesting Tools

Backtest options and equity strategies with [Backtrader](https://www.backtrader.com/), using market data from [Massive.com](https://massive.com/docs) or E*TRADE. Data is validated with Pydantic and stored with SQLAlchemy.

## Features

- **Data**: Sync historical bars (Massive) or quotes/option chain (E*TRADE) into SQLite or Postgres.
- **Backtesting**: Stock strategies (SMA crossover, SMA+RSI) and options strategies (single-leg, covered call, protective put) with custom Backtrader feeds.
- **Time-series forecasting (TSF Options AI)**: **ARIMA** and **gradient boosting (GB)** forecasters; feature pipeline (returns, lags, SMAs, volatility, optional **macro enrichment**); evaluation (directional accuracy, RMSE, backtest returns); **model registry** for forecast runs. **Strategy engine** evaluates options strategies (vertical spreads, straddle, iron condor, **calendar spreads**) using forecast distributions; **break-even analysis** from premium paid; **automated strategy discovery** (`/discover`) ranks all strategies by expected value; optional **historical backtest comparison**. **Research Assistant** (LLM) explains forecasts and strategy rationale with **RAG context** from a built-in financial knowledge base; **E2E** pipeline: forecast → strategy evaluation → explanation. **Risk** module: max drawdown, volatility, **VaR**, **Kelly Criterion position sizing**. See [docs/FORECASTING.md](docs/FORECASTING.md), [docs/STRATEGY_ENGINE.md](docs/STRATEGY_ENGINE.md), [docs/RESEARCH_ASSISTANT.md](docs/RESEARCH_ASSISTANT.md), [docs/RISK_TOOLS.md](docs/RISK_TOOLS.md), and [docs/TSF_OPTIONS_AI_IMPLEMENTATION_PLAN.md](docs/TSF_OPTIONS_AI_IMPLEMENTATION_PLAN.md).
- **Volatility Dashboard**: **Historical Volatility** at 10/20/30/60-day windows; **IV Rank** (0–100 scale); **IV Percentile**; **Expected Move** (1σ, 30-day). Helps time strategy entry — high IV favors premium selling, low IV favors premium buying. See [docs/VOLATILITY.md](docs/VOLATILITY.md).
- **Macro & economic data**: Backend proxy for **FRED**, **BLS**, and **BEA** (`/economic/series`), plus a **Macro & economic** dashboard page to plot normalized time-series alongside your trading metrics. See [docs/ECONOMIC_DATA.md](docs/ECONOMIC_DATA.md).
- **Storage**: SQLAlchemy ORM and repositories for symbol, date range, and contract queries.
- **Web UI**: Next.js dashboard (Options Lab) to create backtests, view history with charts and trade lists, manage default settings, and browse symbols/contracts. Default strategy and symbol from Settings are applied when creating a new backtest.

## Setup

**1. Virtual environment and dependencies**

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**2. Environment variables**

Create a `.env` in the project root (do not commit secrets).

| Variable | Description |
|----------|-------------|
| `JWT_SECRET_KEY` | **Required in production.** 32-byte hex secret for signing auth tokens. Generate: `python -c "import secrets; print(secrets.token_hex(32))"`. Falls back to a dev-only key if unset. |
| `MASSIVE_API_KEY` | [Massive.com](https://massive.com/dashboard/keys) key for `--source massive` sync. |
| `ETrade_CONSUMER_KEY`, `ETrade_CONSUMER_SECRET` | E*TRADE app credentials. |
| `ETrade_ACCESS_TOKEN`, `ETrade_ACCESS_SECRET` | E*TRADE OAuth tokens (optional; UI can fetch these via OAuth and store them in Settings). |
| `ETrade_SANDBOX` | `true` (default) for sandbox, `false` for live. |
| `TRADING_DATABASE_URL` | Default: `sqlite:///trading.db`. Use Postgres URL if needed. |
| `TRADING_DEFAULT_SYMBOL` | Default sync symbol (default: `AAPL`). |
| `TRADING_SYNC_FROM`, `TRADING_SYNC_TO` | Default sync date range. |
| `FRED_API_KEY` | FRED macro database API key. |
| `BLS_API_KEY` | BLS timeseries API key. |
| `BEA_API_KEY` | BEA NIPA API key. |
| `OPENAI_API_KEY` | OpenAI key for LLM explanations in the Research Assistant. Can also be stored per-user in Settings. |

API keys can also be stored in **Settings** (dashboard). Settings take precedence over env vars for sync, trades, and macro data.


## Usage

Use the venv and set `PYTHONPATH=.` when running scripts from the project root.

### Demo data (no API keys)

To demonstrate all features (backtests, forecasting, strategy engine, research) without running sync or using external APIs:

```bash
PYTHONPATH=. python scripts/seed_dummy_data.py
```

This seeds underlying OHLCV bars for AAPL and MSFT (2024-01-01 to 2024-12-31) and one options contract with bars so options backtests work. Uses `TRADING_DATABASE_URL` (default: `sqlite:///trading.db`). Options: `--symbols AAPL`, `--from 2024-01-01`, `--to 2024-06-30`, `--no-options`, `--reset`.

### Sync data

**Massive** (historical OHLCV ± options). Use comma-separated symbols for multiple underlyings:

```bash
PYTHONPATH=. python scripts/sync_data.py --source massive --symbol AAPL --from 2024-01-01 --to 2024-12-31
PYTHONPATH=. python scripts/sync_data.py --source massive --symbol AAPL,MSFT,GOOGL --from 2024-01-01 --to 2024-12-31
```

Flags: `--underlying-only`, `--max-contracts N`, `--expiration-gte`, `--strike-gte`, `--strike-lte`.

**E*TRADE** (quotes and option chain snapshot). Use comma-separated symbols for multiple underlyings:

```bash
PYTHONPATH=. python scripts/sync_data.py --source etrade --symbol AAPL
PYTHONPATH=. python scripts/sync_data.py --source etrade --symbol AAPL,MSFT --options --max-contracts 20
```

### Run backtests (CLI)

**Stock** (require `--from` and `--to`):

```bash
PYTHONPATH=. python scripts/run_backtest.py --strategy sma_crossover --underlying AAPL --from 2024-01-01 --to 2024-12-31
PYTHONPATH=. python scripts/run_backtest.py --strategy sma_rsi --underlying AAPL --from 2024-01-01 --to 2024-12-31
```

**Options**:

```bash
PYTHONPATH=. python scripts/run_backtest.py --strategy single_leg --first-contract --underlying AAPL --from 2024-01-01 --to 2024-12-31
PYTHONPATH=. python scripts/run_backtest.py --strategy covered_call --first-contract --underlying AAPL
PYTHONPATH=. python scripts/run_backtest.py --strategy protective_put --first-contract --underlying AAPL
```

Or by contract: `--contract-id 1` or `--contract-symbol O:AAPL251219C00150000`.  
Strategies: `single_leg`, `sma_crossover`, `sma_rsi`, `covered_call`, `protective_put`. Options: `--cash 100000`, `--no-plot`.

### Time-series forecasting and research (API)

Uses the same underlying data as backtests. Sync data first, then call the API:

- **POST /forecast/run** – Run forecast (model: `arima` or `gb`); optional `include_macro: true` joins stored macro series onto OHLCV features. Returns direction, point forecast, and `macro_enriched` flag. Runs are registered in the model registry.
- **GET /forecast/runs** – List registered forecast runs (optional query: symbol, model_type, limit).
- **POST /forecast/evaluate** – Evaluate forecast quality (directional accuracy, RMSE, backtest return).
- **POST /strategy-engine/evaluate** – Evaluate a single options strategy using a forecast distribution; optional `premium_paid` for break-even computation; optional `include_backtest` with symbol/dates for historical comparison. Response includes `breakeven_prices`.
- **POST /strategy-engine/discover** – Auto-run a forecast, evaluate all strategy types, and return results ranked by expected value. Provide symbol, dates, model, and optional `spread_width_pct`.
- **GET /volatility/{symbol}** – Historical Volatility (10/20/30/60d), IV Rank, IV Percentile, Expected Move (30d). See [docs/VOLATILITY.md](docs/VOLATILITY.md).
- **POST /risk/position-size** – Kelly Criterion and fixed-risk position sizing given win rate, avg win/loss, and capital. See [docs/RISK_TOOLS.md](docs/RISK_TOOLS.md).
- **POST /risk/breakeven** – Break-even prices for any strategy type given premium paid.
- **POST /research/explain** – LLM explanation of forecast and/or strategy with RAG context injected from the built-in financial knowledge base. Placeholder when OPENAI_API_KEY is not set.
- **POST /research/analyze** – E2E: forecast → evaluate strategies → RAG-augmented LLM explanation. OPENAI_API_KEY can be set in Settings or as an env var.
- **POST /research/rag/ingest** – Add a custom document to the RAG knowledge base.
- **POST /research/rag/retrieve** – Debug: retrieve the top-k RAG chunks for a query.

See [docs/FORECASTING.md](docs/FORECASTING.md), [docs/STRATEGY_ENGINE.md](docs/STRATEGY_ENGINE.md), [docs/RESEARCH_ASSISTANT.md](docs/RESEARCH_ASSISTANT.md), and [docs/TSF_OPTIONS_AI_IMPLEMENTATION_PLAN.md](docs/TSF_OPTIONS_AI_IMPLEMENTATION_PLAN.md).

### E*TRADE trading (CLI)

Requires OAuth credentials; use `ETrade_SANDBOX=false` for live.

```bash
PYTHONPATH=. python scripts/etrade_trade.py list-accounts
PYTHONPATH=. python scripts/etrade_trade.py list-orders --account-id-key KEY [--status OPEN]
PYTHONPATH=. python scripts/etrade_trade.py buy-equity --account-id-key KEY --symbol AAPL --quantity 10 [--limit 150.00]
PYTHONPATH=. python scripts/etrade_trade.py sell-equity --account-id-key KEY --symbol AAPL --quantity 5
PYTHONPATH=. python scripts/etrade_trade.py buy-option --account-id-key KEY --symbol AAPL --call --expiry 2025-01-17 --strike 200 --quantity 1
PYTHONPATH=. python scripts/etrade_trade.py cancel --account-id-key KEY --order-id 12345
```

### Web interface (Options Lab)

1. **API** (project root, venv active):

   ```bash
   source venv/bin/activate
   PYTHONPATH=. uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Frontend**:

   ```bash
   cd web && npm install && npm run dev
   ```

   Optional: create `web/.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:8000` to override the API URL (otherwise the app uses the same host as the page on port 8000).

3. Open [http://localhost:3000](http://localhost:3000). You are redirected to the **login page**. Create an account on `/register` (first-time) or sign in. After login the dashboard loads: **Overview**, **Data & symbols**, **Macro & Economics**, **Research & AI**, **Volatility**, **Backtests**, **Trade**, **Settings**. Use **Sign out** in the sidebar to log out. See [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) for token lifetime, multi-user support, and security notes.

### Macro data sync (CLI)

To bulk import the built-in macro presets (FRED/BLS/BEA) via the running API:

```bash
PYTHONPATH=. python3 scripts/sync_economic.py --all-presets --from 2015-01-01 --to 2024-12-31 --to-db
```

**Access from another device on your network:** The dev server binds to `0.0.0.0`, so you can open `http://<your-machine-ip>:3000` from a phone or another PC. The dashboard automatically uses the same host for the API (e.g. opening `http://192.168.1.16:3000` calls `http://192.168.1.16:8000`). No env var is required.

   Start the API with `--host 0.0.0.0` as above. If Next.js warns about cross-origin requests, add your origin (e.g. `http://192.168.1.16:3000`) to `allowedDevOrigins` in `web/next.config.ts`.

   If you see **"TypeError: Failed to fetch"**: (1) Restart the API after changing CORS/config. (2) Allow port 8000 through the host firewall (e.g. `sudo ufw allow 8000`). (3) From the other device, confirm the API is reachable: open `http://<host-ip>:8000` in the browser and check for the JSON response.

## Deployment (AWS)

The entire cloud infrastructure is managed with **AWS CDK (Python)**. Three CDK stacks deploy all required resources; no Serverless Framework CLI is needed.

| Stack | Resources |
|---|---|
| `TradingDataStack` | VPC, NAT gateway, RDS PostgreSQL 16 |
| `TradingApiStack` | Docker-image Lambda, HTTP API Gateway v2, JWT secret (Secrets Manager) |
| `TradingAmplifyStack` | Amplify Hosting (SSR, Next.js App Router) |

```bash
# 1. Install CDK deps
cd infrastructure && pip install -r requirements.txt && cd ..

# 2. Bootstrap CDK once per account/region
cdk bootstrap aws://<ACCOUNT>/<REGION>

# 3. Deploy all stacks (CDK resolves dependency order)
cd infrastructure
cdk deploy --all \
    --context account=<ACCOUNT> \
    --context region=<REGION> \
    --context github_repo=https://github.com/your-org/OptionsLab
```

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for full prerequisites, step-by-step instructions, cost breakdown, and troubleshooting.

## User manual (HTML)

Static pages under [`web/public/user-manual/`](web/public/user-manual/) document how to install and run the stack; the same material is summarized alongside the Markdown guides in [`docs/`](docs/).

| How to read it | Link |
|----------------|------|
| **Browse in GitHub** | Start at **[index.html](web/public/user-manual/index.html)** (sidebar links to other chapters). |
| **Rendered in your browser (no clone, no server)** | Use [HTML Preview](https://htmlpreview.github.io/?https://raw.githubusercontent.com/your-org/OptionsLab/main/web/public/user-manual/index.html) after replacing `your-org` with this repo’s GitHub owner, or open **Raw** on `index.html` in GitHub and paste that `raw.githubusercontent.com` URL into [htmlpreview.github.io](https://htmlpreview.github.io/). |
| **With the web app running** | Open **`/user-manual/index.html`** or **User manual** in the dashboard sidebar. |

## Tests and checks

From project root with venv activated:

```bash
# All tests (API tests use a temp file DB for thread sharing)
PYTHONPATH=. python -m pytest tests/ -v

# With coverage (minimum 80%; scripts excluded). Enforced in .coveragerc.
PYTHONPATH=. python -m pytest tests/ -v --cov --cov-report=term-missing --cov-fail-under=80

# Web lint and build
cd web && npm run lint && npm run build
```

Coverage is reported for: `api/`, `config/`, `data/`, `storage/`, `models/`, `backtrader_feeds/`, `brokers/`, `strategies/`, `features/`, `forecasting/`, `strategy_engine/`, `research_assistant/`, `risk/`, and `volatility/`. The `scripts/` directory is omitted (CLI entry points).

## Project layout

| Directory | Purpose |
|-----------|---------|
| `api/` | FastAPI app: symbols, contracts, bars (paginated), `POST /backtests/run`, lab (saved backtests), user settings, **forecast** (TSF), **strategy engine**, **volatility**, **risk**, **economic** macro proxy, **research** (LLM+RAG). JWT auth (`/auth/register`, `/auth/login`, `/auth/me`). |
| `web/` | Next.js 14 dashboard (App Router). Pages: **Overview** (macro snapshot), **Data & Symbols** (paginated bars/contracts), **Macro & Economics** (FRED/BLS/BEA charts), **Research & AI** (forecast, strategy eval, position sizing, full analysis pipeline), **Volatility** (HV/IV Rank/IV Percentile/Expected Move dashboard with IV vs HV-20 chart), **Backtests** (history, detail, create), **Trade** (E*TRADE), **Settings** (defaults, API keys). Static **user manual** under `public/user-manual/`. |
| `config/` | Settings and env loading. |
| `models/` | Pydantic validation and SQLAlchemy ORM (bars, contracts, backtests, user). |
| `data/` | Massive and E*TRADE clients, sync into DB. |
| `storage/` | Session and repositories. |
| `features/` | Feature engineering for TSF (OHLCV → returns, lags, SMAs, volatility). Same data as backtests. See [docs/DATA_AND_FEATURES.md](docs/DATA_AND_FEATURES.md). |
| `forecasting/` | Time-series models (ARIMA, gradient boosting) and evaluation. See [docs/FORECASTING.md](docs/FORECASTING.md). |
| `strategy_engine/` | Forecast-based options evaluation (spreads, straddle, iron condor, calendar), automated discovery, break-even analysis. See [docs/STRATEGY_ENGINE.md](docs/STRATEGY_ENGINE.md). |
| `research_assistant/` | LLM explanations (OpenAI SDK in `requirements.txt`) with TF-IDF RAG knowledge base. See [docs/RESEARCH_ASSISTANT.md](docs/RESEARCH_ASSISTANT.md). |
| `risk/` | Position sizing (Kelly Criterion, half-Kelly, fixed fractional, max contracts), risk metrics (max drawdown, annualized volatility, historical VaR). See [docs/RISK_TOOLS.md](docs/RISK_TOOLS.md). |
| `volatility/` | Historical Volatility (10/20/30/60d), IV Rank, IV Percentile, Expected Move. See [docs/VOLATILITY.md](docs/VOLATILITY.md). |
| `backtrader_feeds/` | Custom Backtrader feed and DataFrame helpers. |
| `strategies/` | Backtrader strategies and analyzers (single_leg, sma_crossover, sma_rsi, covered_call, protective_put). |
| `brokers/` | E*TRADE order API. |
| `scripts/` | CLI: `sync_data.py`, `run_backtest.py`, `etrade_trade.py`, `sync_economic.py`, `seed_dummy_data.py`. |
| `infrastructure/` | AWS CDK app (Python): VPC, RDS PostgreSQL, Lambda, API Gateway, Amplify Hosting. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). |
| `web/public/user-manual/` | Multi-page **HTML user manual** (served at `/user-manual/`). |
| `docs/` | [AUTHENTICATION.md](docs/AUTHENTICATION.md), [DEPLOYMENT.md](docs/DEPLOYMENT.md), [DATA_AND_FEATURES.md](docs/DATA_AND_FEATURES.md), [FORECASTING.md](docs/FORECASTING.md), [STRATEGY_ENGINE.md](docs/STRATEGY_ENGINE.md), [RESEARCH_ASSISTANT.md](docs/RESEARCH_ASSISTANT.md), [VOLATILITY.md](docs/VOLATILITY.md), [RISK_TOOLS.md](docs/RISK_TOOLS.md), [FRAMEWORKS.md](docs/FRAMEWORKS.md), [ECONOMIC_DATA.md](docs/ECONOMIC_DATA.md), [TSF_OPTIONS_AI_IMPLEMENTATION_PLAN.md](docs/TSF_OPTIONS_AI_IMPLEMENTATION_PLAN.md). Same material is summarized in **`web/public/user-manual/`** (especially **Documentation**). |
| `tests/` | Pytest suite; coverage target 80% (see `.coveragerc`). |

## External docs

- [Massive REST API](https://massive.com/docs)
- [Massive Options REST](https://massive.com/docs/rest/options)
- [Massive Flat Files (Options)](https://massive.com/docs/flat-files/options)

## License

See repository defaults.
