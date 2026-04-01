"""
Break-even price computation for options strategies at expiry.

Break-even is the underlying price at expiry where a strategy's net P&L = 0
(payoff at expiry equals the premium paid).

Key formulas
------------
Straddle (long):
    Lower BE = strike − premium_paid
    Upper BE = strike + premium_paid

Bull Call Spread (debit):
    BE = long_strike + net_debit

Bear Put Spread (debit):
    BE = long_strike − net_debit

Iron Condor (credit):
    Lower BE = put_short − net_credit
    Upper BE = call_short + net_credit

Calendar Spread (simplified):
    Approximated as strike ± net_debit / 2  (exact value is model-dependent
    because at the front-month expiry the back-month still has time value).

When premium_paid is None, an empty list is returned — callers should display
break-even only when premium information is available.
"""

from __future__ import annotations

from typing import Any

from strategy_engine.strategies import StrategyKind


def compute_breakeven_prices(
    kind: StrategyKind,
    params: dict[str, Any],
    premium_paid: float | None = None,
) -> list[float]:
    """
    Return break-even underlying price(s) at expiry for *kind* with *params*.

    Args:
        kind: Strategy type (StrategyKind enum).
        params: Strike parameters matching the strategy type.
        premium_paid: Net premium paid (positive = debit, negative = credit).
                      When None, returns an empty list.

    Returns:
        Sorted list of break-even prices (> 0).  Usually one or two prices.
    """
    if premium_paid is None:
        return []

    net = float(premium_paid)
    prices: list[float] = []

    if kind == StrategyKind.STRADDLE:
        strike = float(params.get("strike", 0.0))
        prices = [strike - net, strike + net]

    elif kind == StrategyKind.VERTICAL_SPREAD_CALL:
        # Bull call spread: debit paid = net
        long_k = float(params.get("long_strike", 0.0))
        prices = [long_k + net]

    elif kind == StrategyKind.VERTICAL_SPREAD_PUT:
        # Bear put spread: debit paid = net
        long_k = float(params.get("long_strike", 0.0))
        prices = [long_k - net]

    elif kind == StrategyKind.IRON_CONDOR:
        # Iron condor: net is negative (we received credit)
        credit = -net
        put_short = float(params.get("put_short", 0.0))
        call_short = float(params.get("call_short", 0.0))
        prices = [put_short - credit, call_short + credit]

    elif kind in (StrategyKind.CALENDAR_SPREAD_CALL, StrategyKind.CALENDAR_SPREAD_PUT):
        # Calendar: simplified — net_debit from params or premium_paid
        strike = float(params.get("strike", 0.0))
        nd = float(params.get("net_debit", net))
        # Approximation: break-evens at ± half the net debit from ATM
        prices = [strike - nd * 0.5, strike + nd * 0.5]

    return sorted(round(p, 2) for p in prices if p > 0)
