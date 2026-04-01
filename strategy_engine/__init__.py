"""
Forecast-based options strategy evaluation.

Evaluates strategies (vertical spreads, straddles, iron condors, calendar spreads)
using a forecast distribution of the underlying price. Produces expected payoff,
payoff diagram data, and risk metrics. Keeps existing Backtrader backtests for
historical validation; this engine is for forward-looking evaluation.

See docs/STRATEGY_ENGINE.md for usage and integration.
"""

from strategy_engine.payoff import (
    payoff_vertical_spread,
    payoff_vertical_spread_call,
    payoff_vertical_spread_put,
    payoff_straddle,
    payoff_iron_condor,
)
from strategy_engine.expected_value import expected_payoff_and_risk
from strategy_engine.strategies import StrategyKind, get_strategy_payoff_fn
from strategy_engine.breakeven import compute_breakeven_prices

__all__ = [
    "payoff_vertical_spread",
    "payoff_vertical_spread_call",
    "payoff_vertical_spread_put",
    "payoff_straddle",
    "payoff_iron_condor",
    "expected_payoff_and_risk",
    "StrategyKind",
    "get_strategy_payoff_fn",
    "compute_breakeven_prices",
]
