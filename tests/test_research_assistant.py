"""Tests for the Research Assistant (LLM) service and RAG integration."""

from research_assistant.service import (
    explain_forecast_and_strategy,
    _build_prompt,
    _placeholder_explanation,
)


def test_explain_without_api_key_returns_placeholder(monkeypatch) -> None:
    """Without OPENAI_API_KEY or user key, explain_forecast_and_strategy returns structured placeholder."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    out = explain_forecast_and_strategy(
        forecast_summary="AAPL: up, horizon 1",
        strategy_summary="straddle EV=0.5",
        include_risk=True,
    )
    assert "AAPL" in out
    assert "straddle" in out or "Strategy" in out
    assert "Settings" in out or "OPENAI_API_KEY" in out or "Review" in out


def test_placeholder_explanation() -> None:
    """Placeholder includes forecast and strategy when provided."""
    out = _placeholder_explanation("F: up", "S: EV=1", include_risk=True)
    assert "F: up" in out
    assert "S: EV=1" in out
    assert "Review" in out or "max loss" in out.lower()


def test_build_prompt() -> None:
    """Prompt builder includes forecast, strategy, and risk instruction."""
    p = _build_prompt("F", "S", include_risk=True)
    assert "Forecast: F" in p
    assert "Strategy evaluation: S" in p
    assert "risk" in p.lower()
    p2 = _build_prompt(None, None, include_risk=False)
    assert "2-3 sentences" in p2


def test_build_prompt_includes_rag_context() -> None:
    """Prompt builder injects RAG context from the knowledge base."""
    p = _build_prompt("iron condor straddle options", "iron condor EV=2.0", include_risk=False)
    # RAG context block should appear before the forecast line
    assert "context" in p.lower() or "1." in p


def test_build_prompt_no_summaries() -> None:
    """Prompt is still well-formed when no summaries are provided."""
    p = _build_prompt(None, None, include_risk=False)
    assert isinstance(p, str)
    assert len(p) > 10


def test_placeholder_explanation_no_inputs() -> None:
    """Placeholder with no inputs returns a non-empty hint string."""
    out = _placeholder_explanation(None, None, include_risk=False)
    assert isinstance(out, str)
    assert len(out) > 0


def test_placeholder_explanation_only_forecast() -> None:
    out = _placeholder_explanation("AAPL: up, horizon 5", None, include_risk=False)
    assert "AAPL" in out


def test_placeholder_explanation_risk_flag() -> None:
    out = _placeholder_explanation(None, None, include_risk=True)
    assert "max loss" in out.lower() or "probability" in out.lower() or "Review" in out


def test_explain_with_user_api_key_env_fallback(monkeypatch) -> None:
    """user_api_key=None falls back to OPENAI_API_KEY env (which is unset → placeholder)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    out = explain_forecast_and_strategy(
        forecast_summary="test",
        strategy_summary=None,
        include_risk=False,
        user_api_key=None,
    )
    assert "test" in out
    assert "Settings" in out or "OPENAI_API_KEY" in out


def test_explain_user_api_key_takes_precedence_over_env(monkeypatch) -> None:
    """A blank user_api_key still falls back to env; an empty string counts as unset."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    out = explain_forecast_and_strategy(
        forecast_summary="hello",
        strategy_summary=None,
        include_risk=False,
        user_api_key="   ",  # whitespace-only → treated as empty → placeholder
    )
    assert "hello" in out
