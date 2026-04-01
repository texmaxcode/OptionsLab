"""
Strategy type definitions for the forecast-based options engine.

Each strategy is defined by a name and parameters (strikes, expiry, etc.).
Payoff logic lives in payoff.py; this module maps strategy kind to payoff function.
"""

from enum import Enum
from typing import Callable

from strategy_engine import payoff


class StrategyKind(str, Enum):
    """Supported strategy types for forecast-based evaluation."""

    VERTICAL_SPREAD_CALL = "vertical_spread_call"  # bull call spread
    VERTICAL_SPREAD_PUT = "vertical_spread_put"    # bear put spread
    STRADDLE = "straddle"
    IRON_CONDOR = "iron_condor"
    CALENDAR_SPREAD_CALL = "calendar_spread_call"   # simplified: long back, short front, same strike
    CALENDAR_SPREAD_PUT = "calendar_spread_put"


def get_strategy_payoff_fn(kind: StrategyKind) -> Callable[..., float]:
    """Return the payoff-at-expiry function for the given strategy kind."""
    if kind == StrategyKind.VERTICAL_SPREAD_CALL:
        return payoff.payoff_vertical_spread_call
    if kind == StrategyKind.VERTICAL_SPREAD_PUT:
        return payoff.payoff_vertical_spread_put
    if kind == StrategyKind.STRADDLE:
        return payoff.payoff_straddle
    if kind == StrategyKind.IRON_CONDOR:
        return payoff.payoff_iron_condor
    if kind == StrategyKind.CALENDAR_SPREAD_CALL:
        return payoff.payoff_calendar_call
    if kind == StrategyKind.CALENDAR_SPREAD_PUT:
        return payoff.payoff_calendar_put
    raise ValueError(f"Unknown strategy kind: {kind}")
