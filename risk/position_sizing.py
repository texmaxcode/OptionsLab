"""
Position sizing for options and equity trading.

Kelly Criterion
---------------
Optimal bet size as a fraction of capital that maximizes long-run growth rate.

Full Kelly:
    f* = (p × b − q) / b
    where  p = win_rate, q = 1 − p, b = avg_win / avg_loss

Half Kelly (recommended):
    Use f*/2 to account for estimation error and to reduce variance.
    Most professional traders use 1/4 to 1/2 Kelly.

Fixed Fractional
----------------
Risk a fixed percentage of capital on each trade.  The number of units to
trade is:  units = (capital × risk_pct) / loss_per_unit

Max Contracts
-------------
Given a per-contract maximum loss (e.g. the debit paid for a spread × multiplier),
compute the maximum number of contracts to stay within a risk budget.

References
----------
- Kelly (1956) — "A New Interpretation of Information Rate"
- Tharp (2008) — "Trade Your Way to Financial Freedom"
"""

from __future__ import annotations


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float | None:
    """
    Full Kelly fraction of capital to risk per trade.

    Args:
        win_rate: Historical win rate (0.0 – 1.0 exclusive).
        avg_win:  Average profit on winning trades (> 0).
        avg_loss: Average loss on losing trades (> 0, unsigned).

    Returns:
        Kelly fraction in [0, 1], or None when inputs are invalid.
        A negative result (edge < 0) is clamped to 0.
    """
    if avg_loss <= 0 or avg_win <= 0 or not (0 < win_rate < 1):
        return None
    b = avg_win / avg_loss
    lose_rate = 1.0 - win_rate
    f = (win_rate * b - lose_rate) / b
    return max(0.0, min(f, 1.0))


def half_kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float | None:
    """
    Half-Kelly: more conservative than full Kelly, reduces variance significantly.

    Most practitioners recommend half Kelly or less to account for model
    uncertainty and sequential drawdowns.
    """
    full = kelly_fraction(win_rate, avg_win, avg_loss)
    return None if full is None else full / 2.0


def fixed_risk_size(
    capital: float,
    risk_pct: float,
    loss_per_unit: float,
) -> float | None:
    """
    Fixed fractional position size.

    How many units (shares / spreads) to trade to risk exactly *risk_pct* %
    of capital on this trade.

    Args:
        capital:       Total account capital in $.
        risk_pct:      Maximum risk per trade as a percentage (e.g. 1.0 = 1 %).
        loss_per_unit: Maximum dollar loss per unit (e.g. debit paid per spread).

    Returns:
        Number of units (float), or None when inputs are invalid.
    """
    if capital <= 0 or risk_pct <= 0 or loss_per_unit <= 0:
        return None
    dollar_risk = capital * risk_pct / 100.0
    return dollar_risk / loss_per_unit


def max_contracts(
    capital: float,
    max_risk_pct: float,
    max_loss_per_contract: float,
    contract_multiplier: int = 100,
) -> int | None:
    """
    Maximum options contracts given a risk budget and per-contract max loss.

    The per-contract max loss is:
        max_loss_per_contract × contract_multiplier
    (e.g. $2.00 debit × 100 shares = $200 max loss per contract)

    Args:
        capital:                 Total account capital in $.
        max_risk_pct:            Maximum total risk as % of capital.
        max_loss_per_contract:   Premium paid per contract (per-share amount, e.g. $2.00).
        contract_multiplier:     Shares per contract (default 100).

    Returns:
        Max number of contracts (int ≥ 0), or None when inputs are invalid.
    """
    if any(x <= 0 for x in [capital, max_risk_pct, max_loss_per_contract, contract_multiplier]):
        return None
    risk_budget = capital * max_risk_pct / 100.0
    cost_per_contract = max_loss_per_contract * contract_multiplier
    return max(0, int(risk_budget / cost_per_contract))
