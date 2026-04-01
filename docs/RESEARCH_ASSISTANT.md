# Research Assistant (LLM)

The Research Assistant generates short natural-language explanations of forecasts and strategy evaluation. It is used by the E2E **POST /research/analyze** flow and can be called directly via **POST /research/explain**.

## Behavior

- **With OPENAI_API_KEY set (env or user settings):** Calls OpenAI (gpt-4o-mini) with a structured, RAG-augmented prompt to produce 2–3 sentences and an optional risk summary.
- **Without API key:** Returns a structured placeholder that includes the forecast and strategy summary so the pipeline still works. The response notes that the key can be set in Settings or as an env var.

## RAG (Retrieval-Augmented Generation)

Phase 4.2 — **now implemented** in `research_assistant/rag.py`.

The RAG module maintains an in-memory knowledge base of financial concepts:
- Options strategy definitions (bull call spread, bear put spread, straddle, iron condor, calendar spread)
- Greeks (delta, theta, vega, implied volatility)
- Risk concepts (probability of profit, max loss, expected value, VaR, max drawdown)
- Forecasting concepts (ARIMA, gradient boosting, directional accuracy, horizon)
- Macro / economic context (GDP, CPI, VIX, unemployment, treasury yield)

At query time, the top-3 most relevant chunks are retrieved using **TF-IDF cosine similarity** and prepended to the LLM prompt as "Relevant financial context". If **`chromadb`** is installed (`pip install chromadb`), it is used instead for better semantic search.

### RAG API

- **POST /research/rag/ingest** – Add a custom document to the knowledge base (topic field optional, defaults to "custom"). Documents are available immediately for all subsequent `/explain` and `/analyze` calls. In-memory only by default; persisted across restarts when a chromadb persistent client is configured.
- **POST /research/rag/retrieve** – Debug endpoint: retrieve the top_k chunks for a query to inspect what context would be injected into an LLM prompt.

### Adding custom documents

```python
# Via API
POST /research/rag/ingest
{ "text": "Our proprietary rule: avoid iron condors in VIX > 30 environments.", "topic": "internal_rule" }
```

### chromadb (optional)

If `chromadb` is installed the module automatically uses it (in-process, no server required). For persistence across restarts, configure a persistent chromadb client in `research_assistant/rag.py`.

## OpenAI API key

The key can be set in two ways (user settings take precedence over env var):
1. **User settings:** Go to Settings → AI & Research Assistant → enter `sk-...` key. Stored encrypted in the user's DB record.
2. **Environment variable:** `OPENAI_API_KEY=sk-...` in the server environment.

## API

- **POST /research/explain** – Body: `forecast_summary`, `strategy_summary` (optional), `include_risk`. Returns `explanation` text.
- **POST /research/analyze** – Full pipeline: load data → run forecast → evaluate requested strategies → build summary → call Research Assistant with RAG context → return combined response (forecast direction/mean, strategy results, explanation).
- **POST /research/rag/ingest** – Add a custom document to the knowledge base.
- **POST /research/rag/retrieve** – Retrieve chunks for a query (debug).

## UI Layout

The **Research & AI** page (`/dashboard/research`) contains four cards, in order:

1. **Run forecast** — Symbol, From/To date, Model (ARIMA / Gradient Boost), and Horizon inputs in a responsive grid. Clicking "Run" calls `POST /forecast/run`. The result shows direction badge (up/down/flat) and the final forecast value inline.

2. **Evaluate strategy** — Four rows:
   - *Row 1*: Strategy type, Forecast mean, Forecast std, and Premium paid — all in a 4-column grid.
   - *Row 2* (conditional): Strategy-specific strike inputs (rendered as a 2/4-column grid based on the selected strategy).
   - *Row 3*: "Include historical backtest" checkbox and **Evaluate strategy** button.
   - *Results* (after submit): A 2×2 metric grid (Expected Value / P(profit) / Max Loss / Max Gain), break-even amber badges, and the payoff diagram chart.

3. **Full analysis** — Symbol, dates, and horizon in a responsive grid; one "Analyze" button. Calls `POST /research/analyze` (full pipeline). Result shows forecast direction, mean, strategy count, and the LLM explanation.

4. **Position Sizing** — Capital, win rate, avg win/loss, max risk %, and optional max loss per contract in a 3-column grid. Results: four metric cards (Full Kelly, Half Kelly ✓, Fixed Risk, Max Contracts).

5. **Recent forecast runs** — Lazy-loaded list of the last 15 registered forecast runs (refresh button).

## Package layout

- `research_assistant/service.py` – `explain_forecast_and_strategy()`; placeholder vs OpenAI call; RAG-augmented prompt builder; accepts `user_api_key` param.
- `research_assistant/rag.py` – Knowledge base, TF-IDF retrieval, optional chromadb backend, `add_document()`, `retrieve()`, `build_rag_context()`.
