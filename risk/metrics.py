"""
Risk metrics: max drawdown and volatility.

Used by backtest results and strategy evaluation. Exposed via API for
the Research Assistant to cite.
"""

from typing import Sequence


def max_drawdown(equity_curve: Sequence[float]) -> float:
    """
    Maximum drawdown from an equity curve (ordered in time).

    Returns a non-negative number: the largest peak-to-trough decline
    as a fraction of the peak (e.g. 0.15 = 15% drawdown).
    """
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def volatility_annualized(returns: Sequence[float], periods_per_year: int = 252) -> float:
    """
    Annualized volatility (std of returns) for daily data.

    Assumes returns are period returns (e.g. daily). Multiplies by sqrt(periods_per_year).
    """
    if not returns or len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return (variance ** 0.5) * (periods_per_year ** 0.5)


def var_historical(
    returns: Sequence[float],
    alpha: float = 0.95,
) -> float:
    """
    Historical Value at Risk (VaR): the loss level exceeded with probability (1 - alpha).

    Returns are period returns (e.g. daily). VaR is returned as a positive number
    representing the loss (e.g. 0.02 = 2% loss). So for alpha=0.95, 95% of the time
    the loss is no worse than this.
    """
    if not returns:
        return 0.0
    sorted_returns = sorted(returns)
    n = len(sorted_returns)
    # (1 - alpha) quantile: e.g. alpha=0.95 -> 5% quantile (worst 5% of returns)
    q = (1 - alpha) * n
    idx = min(max(0, int(q) - 1), n - 1)
    worst = sorted_returns[idx]
    # VaR as positive loss: -worst when worst is negative
    return float(-worst) if worst < 0 else 0.0
