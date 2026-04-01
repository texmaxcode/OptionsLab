# TSF Options AI – System Architecture

This document describes the **Time Series Forecasting for Options Trading** system built on top of the Options Backtesting codebase. All phases are complete and fully operational.

## Implementation status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 – Data & features | ✅ Complete | `features/` pipeline, OHLCV loader, macro features (`features/macro_features.py`) |
| Phase 2 – Forecasting models | ✅ Complete | ARIMA + GB (`scikit-learn`); model registry; evaluation metrics; optional macro enrichment |
| Phase 3 – Strategy engine | ✅ Complete | All spread types incl. calendar spreads; payoff diagrams; compare-to-backtest; `/discover` |
| Phase 4.1 – LLM research assistant | ✅ Complete | RAG-augmented prompts via OpenAI; placeholder when no key; user settings key |
| Phase 4.2 – RAG pipeline | ✅ Complete | `research_assistant/rag.py`; TF-IDF + optional chromadb; ingest/retrieve API |
| Phase 5 – E2E flow + risk module | ✅ Complete | `/research/analyze`; VaR and drawdown |
| Phase 5.4 – Automated strategy discovery | ✅ Complete | `POST /strategy-engine/discover`; auto-ranks all strategies by EV |

See `docs/STRATEGY_ENGINE.md`, `docs/RESEARCH_ASSISTANT.md`, and `docs/FORECASTING.md` for detailed API references.

---

## 1. System objectives

| Objective | Implementation |
|-----------|----------------|
| Forecast asset price movements using time-series models | `forecasting/` — ARIMA and GB models; `POST /forecast/run`, `GET /forecast/runs` |
| Evaluate options strategies using forecasts | `strategy_engine/` — vertical spreads, straddles, iron condor, calendar spreads; `POST /strategy-engine/evaluate`, `POST /strategy-engine/discover` |
| LLM explanations and research summaries | `research_assistant/` — RAG-augmented prompts via OpenAI; `POST /research/explain`, `POST /research/analyze` |
| Strong system design (ML + finance + LLM) | Clear separation: data → features → forecasting → strategy engine → research assistant; full REST API and Next.js UI |

---

## 2. Core system components

| Component | Location | Description |
|-----------|----------|-------------|
| **Market Data Pipeline** | `data/`, `storage/`, `models/` | Massive (historical OHLCV) and E*TRADE (quotes, option chain) sync. SQLAlchemy repositories for all storage operations. |
| **Feature Engineering** | `features/` | OHLCV features: close-to-close returns, lagged returns, SMAs, rolling volatility, next-period target. Optional macro enrichment via `features/macro_features.py`. |
| **Time-Series Forecasting** | `forecasting/` | ARIMA (`statsmodels`) and gradient boosting (`scikit-learn HistGradientBoostingRegressor`). Evaluation: directional accuracy, RMSE, MAE, backtest-signal returns. JSON model registry. |
| **Options Strategy Engine** | `strategy_engine/` | European-style payoff functions for all six strategy types. Forecast distribution → expected value, probability of profit, max loss/gain, payoff diagram. Historical backtest comparison via `include_backtest`. Automated ranking via `/discover`. |
| **Research Assistant (LLM)** | `research_assistant/` | RAG-augmented prompt construction. OpenAI `gpt-4o-mini` when key is configured; structured placeholder otherwise. API key stored per-user in Settings or via `OPENAI_API_KEY` env var. |
| **RAG pipeline** | `research_assistant/rag.py` | 20+ built-in financial knowledge chunks (strategy definitions, Greeks, risk concepts, forecasting, macro). TF-IDF cosine retrieval with optional chromadb backend. `/research/rag/ingest` and `/research/rag/retrieve` endpoints. |
| **Risk Module** | `risk/` | `max_drawdown`, `volatility_annualized`, `var_historical`. Used by strategy engine and backtest lab. |

---

## 3. Architecture: data flow

```
Market Data (Massive / E*TRADE)
        │
        ▼
  storage/  ← SQLAlchemy ORM ← models/sql_models.py
  (underlying_bars, options_contracts, options_bars, economic_series_points)
        │
        ├──► Backtesting engine (Backtrader)
        │         backtrader_feeds/ → strategies/ → api/services/run_backtest.py
        │
        └──► TSF pipeline
                  │
                  ▼
            features/
            load_underlying_series() + build_ohlcv_features()
            + join_macro_features()  (optional, uses economic_series_points)
                  │
                  ▼
            forecasting/
            ARIMAForecaster | GBForecaster
            → direction, point forecast, forecast_std
                  │
                  ▼
            strategy_engine/
            distribution_from_forecast() → expected_payoff_and_risk()
            → EV, PoP, max_loss, payoff_diagram
                  │
                  ▼
            research_assistant/
            rag.retrieve() → build_rag_context()
            → _build_prompt() → OpenAI (or placeholder)
            → explanation text
```

---

## 4. Technology stack

| Area | Technology |
|------|-----------|
| **Language / runtime** | Python 3.12 |
| **Time-series / stats** | `statsmodels` (ARIMA), `scikit-learn` (gradient boosting) |
| **Feature / data** | `pandas`, `numpy` |
| **RAG retrieval** | TF-IDF (built-in); `chromadb` if installed (optional) |
| **LLM** | OpenAI API (`gpt-4o-mini`); graceful placeholder fallback |
| **Backend** | FastAPI with routers: `forecast`, `strategy-engine`, `research`, `economic`, `backtests`, `lab`, `user`, `auth` |
| **Frontend** | Next.js 15 (App Router); Research & AI, Macro & Economics, Backtests, Trade, Data & Symbols, Settings pages |
| **Infrastructure** | AWS CDK (Python): Lambda + Docker, RDS PostgreSQL, API Gateway, Amplify Hosting |

---

## 5. Directory layout

```text
OptionsLab/
├── api/                    # FastAPI application, routers, schemas, auth
│   └── routers/            # backtests, backtests_lab, contracts, economic, etrade_*,
│                           # forecasting, research, strategies, strategy_engine, sync, user
├── data/                   # Massive + E*TRADE sync clients
├── features/               # Feature engineering: OHLCV features, macro enrichment
├── forecasting/            # ARIMA, GB forecasters; evaluation; model registry
├── strategy_engine/        # Payoff functions; expected value; strategy discovery
├── research_assistant/     # LLM service; RAG knowledge base
├── risk/                   # max_drawdown, volatility, VaR
├── storage/                # SQLAlchemy session, repositories
├── models/                 # ORM models (sql_models.py) and ingestion schemas (pydantic_models.py)
├── strategies/             # Backtrader strategy implementations
├── backtrader_feeds/       # Backtrader data feeds and DataFrame converters
├── brokers/                # Alpaca and E*TRADE order execution
├── config/                 # Environment-based settings
├── infrastructure/         # AWS CDK stacks (data, api, amplify)
├── scripts/                # CLI tools: sync, backtest, economic data, seed
├── web/                    # Next.js dashboard (Options Lab)
├── tests/                  # 244 pytest tests covering all modules
└── docs/                   # This and other reference documents
```

---

## 6. Key design principles

- **Shared data layer:** Backtesting and forecasting use the same `UnderlyingBarRepository` and `underlying_bars_to_dataframe` conversion, so results are directly comparable for any symbol/date range.
- **Modular pipeline:** Each layer (features → forecasting → strategy → research) has a clean interface and can be used independently via the API.
- **Graceful degradation:** The Research Assistant returns structured placeholders when no LLM key is configured. RAG falls back from chromadb to TF-IDF if the optional dependency is absent.
- **User-configurable secrets:** API keys (Massive, Alpaca, E*TRADE, FRED, BLS, BEA, OpenAI) are stored per-user in the database and take precedence over environment variables, so the system works in both single-user and multi-user deployments.
- **Environment parity:** Dev, staging, and production use the same CDK stacks with per-environment configuration in `infrastructure/config.py`.
