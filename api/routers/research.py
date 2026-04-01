"""
Research API: explanations (LLM), E2E analyze (forecast + strategies + explanation),
and RAG document ingestion.

See docs/TSF_OPTIONS_AI_IMPLEMENTATION_PLAN.md Phase 4 and 5.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api import auth_utils
from api.schemas import (
    ResearchAnalyzeRequest,
    ResearchAnalyzeResponse,
    ResearchExplainRequest,
    ResearchExplainResponse,
)
from api.user_settings_utils import extract_unmasked_settings, load_user_settings
from models.sql_models import UserModel
from research_assistant import explain_forecast_and_strategy
from research_assistant.rag import add_document, retrieve
from storage import session_scope

router = APIRouter(prefix="/research", tags=["research"])


def _user_openai_key(user: UserModel) -> str | None:
    """Return the user's stored OpenAI API key from the database, or None if not set.

    Always loads a fresh row by ``user.id`` so the key saved in Settings is honored
    even if the ``UserModel`` from the auth dependency was attached to an older
    session or missing ``settings_json``.
    """
    with session_scope() as session:
        row = session.get(UserModel, user.id)
        if row is None:
            return None
        data = load_user_settings(row)
    extracted = extract_unmasked_settings(data, keys=("openai_api_key",))
    raw = extracted.get("openai_api_key")
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


@router.post("/explain", response_model=ResearchExplainResponse)
async def explain(
    body: ResearchExplainRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """
    Get an LLM-generated explanation of the forecast and/or strategy evaluation.

    RAG context from the built-in financial knowledge base is automatically
    injected into the prompt when OpenAI is available. If OPENAI_API_KEY is not
    set in the environment or user settings, returns a structured placeholder.
    """
    try:
        explanation = explain_forecast_and_strategy(
            forecast_summary=body.forecast_summary,
            strategy_summary=body.strategy_summary,
            include_risk=body.include_risk,
            user_api_key=_user_openai_key(current_user),
        )
        return ResearchExplainResponse(success=True, explanation=explanation, error=None)
    except Exception as e:
        return ResearchExplainResponse(
            success=False, explanation="", error=str(e)
        )


@router.post("/analyze", response_model=ResearchAnalyzeResponse)
async def analyze(
    body: ResearchAnalyzeRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """
    Run the full pipeline: forecast → strategy evaluation → LLM explanation.

    Uses the same data as backtesting. Returns combined forecast, strategy
    results, and natural-language explanation (with RAG context when LLM is
    available).
    """
    from features import load_underlying_series, build_ohlcv_features
    from forecasting import ARIMAForecaster
    from strategy_engine import expected_payoff_and_risk
    from strategy_engine.expected_value import distribution_from_forecast
    from strategy_engine.strategies import StrategyKind

    from api.utils import parse_iso_date

    from_dt = parse_iso_date(body.from_date)
    to_dt = parse_iso_date(body.to_date)
    if from_dt is None or to_dt is None:
        return ResearchAnalyzeResponse(
            success=False,
            symbol=body.symbol,
            error="Invalid date format. Use YYYY-MM-DD.",
        )

    try:
        df = load_underlying_series(body.symbol, from_date=from_dt, to_date=to_dt)
    except Exception as e:
        return ResearchAnalyzeResponse(
            success=False, symbol=body.symbol, error=f"Failed to load data: {e}"
        )

    if df.empty or len(df) < 10:
        return ResearchAnalyzeResponse(
            success=False,
            symbol=body.symbol,
            error="Insufficient data. Sync data for this symbol and range.",
        )

    try:
        feat = build_ohlcv_features(df, drop_na=True)
        if feat.empty:
            return ResearchAnalyzeResponse(
                success=False, symbol=body.symbol, error="Feature build produced no rows."
            )
        model = ARIMAForecaster(order=(1, 0, 0)).fit(feat["close"])
        pred = model.predict(horizon=body.horizon)
        forecast_mean = float(pred.iloc[-1])
        forecast_direction = model.predict_direction(horizon=body.horizon)
        train_std = feat["close"].pct_change().dropna().std()
        forecast_std = float(train_std * (body.horizon ** 0.5)) if train_std and body.horizon else None
    except Exception as e:
        return ResearchAnalyzeResponse(
            success=False, symbol=body.symbol, error=f"Forecast failed: {e}"
        )

    strategy_results = []
    params_shared = body.strategy_params or {}
    for st in body.strategy_types:
        try:
            kind = StrategyKind(st)
        except ValueError:
            continue
        params = dict(params_shared)
        if kind in (StrategyKind.VERTICAL_SPREAD_CALL, StrategyKind.VERTICAL_SPREAD_PUT):
            params.setdefault("long_strike", forecast_mean * 0.98)
            params.setdefault("short_strike", forecast_mean * 1.02)
        elif kind == StrategyKind.IRON_CONDOR:
            params.setdefault("put_long", forecast_mean * 0.92)
            params.setdefault("put_short", forecast_mean * 0.97)
            params.setdefault("call_short", forecast_mean * 1.03)
            params.setdefault("call_long", forecast_mean * 1.08)
        elif kind == StrategyKind.STRADDLE:
            params.setdefault("strike", forecast_mean)
        dist = distribution_from_forecast(forecast_mean, forecast_std)
        try:
            res = expected_payoff_and_risk(kind, params, dist)
            strategy_results.append(
                {"strategy_type": st, "params": params, **res}
            )
        except Exception:
            continue

    forecast_summary = (
        f"{body.symbol}: direction {forecast_direction}, horizon {body.horizon}, "
        f"mean ~{forecast_mean:.2f}"
    )
    strategy_summary = None
    if strategy_results:
        parts = [
            f"{r['strategy_type']}: EV={r['expected_value']:.2f}, PoP={r['probability_of_profit']:.2f}"
            for r in strategy_results
        ]
        strategy_summary = "; ".join(parts)

    try:
        explanation = explain_forecast_and_strategy(
            forecast_summary=forecast_summary,
            strategy_summary=strategy_summary,
            include_risk=True,
            user_api_key=_user_openai_key(current_user),
        )
    except Exception:
        explanation = forecast_summary + (" " + strategy_summary if strategy_summary else "")

    return ResearchAnalyzeResponse(
        success=True,
        symbol=body.symbol,
        forecast_direction=forecast_direction,
        forecast_mean=forecast_mean,
        strategy_results=strategy_results,
        explanation=explanation,
        error=None,
    )


# ---------------------------------------------------------------------------
# RAG endpoints
# ---------------------------------------------------------------------------

class RagIngestRequest(BaseModel):
    text: str
    topic: str = "custom"


class RagIngestResponse(BaseModel):
    success: bool
    message: str


class RagRetrieveRequest(BaseModel):
    query: str
    top_k: int = 3


class RagRetrieveResponse(BaseModel):
    success: bool
    chunks: list[str]


@router.post("/rag/ingest", response_model=RagIngestResponse)
async def rag_ingest(
    body: RagIngestRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """
    Add a custom document to the RAG knowledge base.

    The document is available immediately for future /research/explain and
    /research/analyze calls. Documents are stored in-process (not persisted
    across server restarts unless chromadb with a persistent client is used).
    """
    if not body.text.strip():
        return RagIngestResponse(success=False, message="text must not be empty")
    try:
        add_document(text=body.text.strip(), topic=body.topic)
        return RagIngestResponse(
            success=True,
            message=f"Document ingested into topic '{body.topic}'.",
        )
    except Exception as e:
        return RagIngestResponse(success=False, message=str(e))


@router.post("/rag/retrieve", response_model=RagRetrieveResponse)
async def rag_retrieve(
    body: RagRetrieveRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """
    Retrieve top_k relevant knowledge chunks for a query (for debugging RAG).

    Returns the raw chunks that would be injected into an LLM prompt.
    """
    try:
        chunks = retrieve(body.query, top_k=body.top_k)
        return RagRetrieveResponse(success=True, chunks=chunks)
    except Exception:
        return RagRetrieveResponse(success=False, chunks=[])
