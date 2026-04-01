"""
Research Assistant: LLM-powered explanations of forecasts and strategy evaluation.

Provides a single interface to generate short explanations and risk summaries
from structured forecast and strategy data. Optional RAG can be added later.
See docs/RESEARCH_ASSISTANT.md.
"""

from research_assistant.service import explain_forecast_and_strategy

__all__ = ["explain_forecast_and_strategy"]
