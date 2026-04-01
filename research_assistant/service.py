"""
LLM service for research explanations.

Uses OPENAI_API_KEY (environment variable or passed explicitly from user settings)
when set; otherwise returns a placeholder so the pipeline works without a key.

RAG is automatically applied when OpenAI is available: relevant financial
knowledge chunks are retrieved from the built-in knowledge base (rag.py) and
prepended to the LLM prompt for richer, more accurate explanations.
"""

import logging
import os

from research_assistant.rag import build_rag_context

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI as OpenAIClient
except ImportError:  # pragma: no cover - exercised when openai not installed
    OpenAIClient = None

# Shown when no API key is configured (env or Settings)
_PLACEHOLDER_HINT_NO_KEY = (
    "(Add an OpenAI API key in Settings → AI & Research, or set OPENAI_API_KEY "
    "in the environment for the API server.)"
)


def explain_forecast_and_strategy(
    forecast_summary: str | None = None,
    strategy_summary: str | None = None,
    include_risk: bool = True,
    user_api_key: str | None = None,
) -> str:
    """
    Generate a short natural-language explanation of the forecast and/or strategy.

    Parameters
    ----------
    forecast_summary:
        Human-readable description of the forecast result.
    strategy_summary:
        Human-readable description of strategy evaluation result(s).
    include_risk:
        Whether to request a risk summary from the LLM.
    user_api_key:
        OpenAI API key from user settings (takes precedence over env var).
    """
    api_key = (user_api_key or "").strip() or os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _placeholder_explanation(
            forecast_summary=forecast_summary,
            strategy_summary=strategy_summary,
            include_risk=include_risk,
        )
    if OpenAIClient is None:
        return (
            _placeholder_explanation(
                forecast_summary=forecast_summary,
                strategy_summary=strategy_summary,
                include_risk=include_risk,
            ).replace(
                _PLACEHOLDER_HINT_NO_KEY,
                " The OpenAI Python SDK is not installed on the server. Run: pip install openai",
            )
        )
    return _call_llm(
        forecast_summary=forecast_summary,
        strategy_summary=strategy_summary,
        include_risk=include_risk,
        api_key=api_key,
    )


def _placeholder_explanation(
    forecast_summary: str | None,
    strategy_summary: str | None,
    include_risk: bool,
) -> str:
    """Structured placeholder when no LLM is configured."""
    parts = []
    if forecast_summary:
        parts.append(f"Forecast: {forecast_summary}")
    if strategy_summary:
        parts.append(f"Strategy: {strategy_summary}")
    if include_risk:
        parts.append("Review max loss and probability of profit before trading.")
    if not parts:
        return "Provide forecast and/or strategy summary for an explanation."
    return " ".join(parts) + " " + _PLACEHOLDER_HINT_NO_KEY


def _call_llm(
    forecast_summary: str | None,
    strategy_summary: str | None,
    include_risk: bool,
    api_key: str,
) -> str:
    """Call OpenAI API with RAG-augmented prompt. Falls back on error with a distinct note."""
    assert OpenAIClient is not None
    try:
        client = OpenAIClient(api_key=api_key)
        prompt = _build_prompt(forecast_summary, strategy_summary, include_risk)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=350,
        )
        if resp.choices and resp.choices[0].message.content:
            return resp.choices[0].message.content.strip()
    except Exception as e:  # pragma: no cover - external API
        logger.warning("OpenAI chat completion failed: %s", e, exc_info=True)
        base = _placeholder_explanation(forecast_summary, strategy_summary, include_risk)
        return (
            base.replace(
                _PLACEHOLDER_HINT_NO_KEY,
                "(OpenAI request failed — check API key, billing, and network. "
                f"Error: {e!s})",
            )
        )
    logger.warning("OpenAI returned empty message content")
    return _placeholder_explanation(forecast_summary, strategy_summary, include_risk)


def _build_prompt(
    forecast_summary: str | None,
    strategy_summary: str | None,
    include_risk: bool,
) -> str:
    """Build an RAG-augmented prompt for the LLM."""
    # Build a query from available summaries for RAG retrieval
    query_parts = []
    if forecast_summary:
        query_parts.append(forecast_summary)
    if strategy_summary:
        query_parts.append(strategy_summary)
    query = " ".join(query_parts) if query_parts else "options strategy forecast"

    rag_context = build_rag_context(query, top_k=3)

    lines = [
        "You are a concise options trading analyst. In 2-3 sentences, explain the following for a trader:",
    ]
    if rag_context:
        lines.append("")
        lines.append(rag_context)
        lines.append("")
    if forecast_summary:
        lines.append(f"Forecast: {forecast_summary}")
    if strategy_summary:
        lines.append(f"Strategy evaluation: {strategy_summary}")
    if include_risk:
        lines.append("Include a brief risk note (max loss, probability of profit).")
    return "\n".join(lines)
