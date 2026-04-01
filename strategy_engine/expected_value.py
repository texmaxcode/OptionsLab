"""
Expected payoff and risk metrics from a forecast distribution.

Takes a discrete distribution of underlying price at expiry (e.g. from ARIMA
forecast + uncertainty or bootstrap) and strategy parameters; returns
expected value, probability of profit, max loss, and payoff diagram data for UI.
"""

from typing import Any

from strategy_engine.strategies import StrategyKind, get_strategy_payoff_fn


def _strike_bounds_for_diagram(kind: StrategyKind, params: dict[str, Any]) -> tuple[float, float] | None:
    """
    Min/max underlying prices to plot for the payoff diagram.

    Uses strategy strikes with padding so the full piecewise-linear payoff is visible.
    The forecast distribution's price range is *not* used here: when ``forecast_std``
    is missing the distribution collapses to a single point, which previously forced
    the diagram to sample ``mean, mean+1, ...`` and produced a misleading straight line.
    """
    try:
        if kind in (StrategyKind.VERTICAL_SPREAD_CALL, StrategyKind.VERTICAL_SPREAD_PUT):
            lo = float(params["long_strike"])
            hi = float(params["short_strike"])
        elif kind == StrategyKind.STRADDLE:
            k = float(params["strike"])
            lo = hi = k
        elif kind == StrategyKind.IRON_CONDOR:
            lo = float(params["put_long"])
            hi = float(params["call_long"])
        elif kind in (StrategyKind.CALENDAR_SPREAD_CALL, StrategyKind.CALENDAR_SPREAD_PUT):
            k = float(params["strike"])
            lo = hi = k
        else:
            return None
    except (KeyError, TypeError, ValueError):
        return None

    span = hi - lo
    # Padding: fraction of strike spread, % of spot, or a few dollars — never zero for single-strike
    pad = max(span * 0.25, lo * 0.08 if lo > 0 else 0.0, 5.0)
    return lo - pad, hi + pad


def _fallback_diagram_bounds(
    distribution: list[tuple[float, float]],
) -> tuple[float, float]:
    """When strike-based bounds are unavailable, expand distribution min/max."""
    prices = [p for p, _ in distribution]
    if not prices:
        return 0.0, 100.0
    s_min, s_max = min(prices), max(prices)
    if s_max > s_min:
        pad = max((s_max - s_min) * 0.1, 1.0)
        return s_min - pad, s_max + pad
    c = s_min
    pad = max(abs(c) * 0.15, 5.0)
    return c - pad, c + pad


def _payoff_for_kind(
    kind: StrategyKind,
    params: dict[str, Any],
    underlying: float,
) -> float:
    """Dispatch to the correct payoff function with params."""
    fn = get_strategy_payoff_fn(kind)
    if kind == StrategyKind.VERTICAL_SPREAD_CALL:
        return fn(
            underlying,
            params["long_strike"],
            params["short_strike"],
        )
    if kind == StrategyKind.VERTICAL_SPREAD_PUT:
        return fn(
            underlying,
            params["long_strike"],
            params["short_strike"],
        )
    if kind == StrategyKind.STRADDLE:
        return fn(underlying, params["strike"])
    if kind == StrategyKind.IRON_CONDOR:
        return fn(
            underlying,
            params["put_short"],
            params["put_long"],
            params["call_short"],
            params["call_long"],
        )
    if kind == StrategyKind.CALENDAR_SPREAD_CALL:
        return fn(underlying, params["strike"], params["net_debit"])
    if kind == StrategyKind.CALENDAR_SPREAD_PUT:
        return fn(underlying, params["strike"], params["net_debit"])
    raise ValueError(f"Unhandled strategy kind: {kind}")


def expected_payoff_and_risk(
    strategy_kind: StrategyKind,
    params: dict[str, Any],
    distribution: list[tuple[float, float]],
    *,
    payoff_points: int = 50,
) -> dict[str, Any]:
    """
    Compute expected payoff and risk metrics from a discrete forecast distribution.

    Args:
        strategy_kind: One of StrategyKind (vertical spread, straddle, iron condor).
        params: Strategy parameters (strikes, etc.). Keys depend on strategy:
            - vertical_spread_call/put: long_strike, short_strike
            - straddle: strike
            - iron_condor: put_long, put_short, call_short, call_long
        distribution: List of (underlying_price, probability). Probabilities should sum to 1.
        payoff_points: Number of points for payoff diagram (spread over price range).

    Returns:
        Dict with expected_value, probability_of_profit, max_loss, max_gain,
        payoff_diagram (list of {underlying, payoff} for UI).
    """
    if not distribution:
        return {
            "expected_value": 0.0,
            "probability_of_profit": 0.0,
            "max_loss": 0.0,
            "max_gain": 0.0,
            "payoff_diagram": [],
        }
    total_prob = sum(p for _, p in distribution)
    if abs(total_prob - 1.0) > 0.01:
        # Normalize
        distribution = [(s, p / total_prob) for s, p in distribution]
    expected = 0.0
    prob_profit = 0.0
    payoffs_seen: list[float] = []
    for price, prob in distribution:
        payoff_val = _payoff_for_kind(strategy_kind, params, price)
        expected += payoff_val * prob
        if payoff_val > 0:
            prob_profit += prob
        payoffs_seen.append(payoff_val)
    max_loss = min(payoffs_seen) if payoffs_seen else 0.0
    max_gain = max(payoffs_seen) if payoffs_seen else 0.0
    # Payoff diagram: sample across a strike-centered range (not distribution min/max).
    # A collapsed distribution (single price when std is missing) used to produce a
    # degenerate domain and a chart that looked like a single straight line.
    bounds = _strike_bounds_for_diagram(strategy_kind, params)
    if bounds is None:
        s_min, s_max = _fallback_diagram_bounds(distribution)
    else:
        s_min, s_max = bounds
    step = (s_max - s_min) / (payoff_points - 1) if payoff_points > 1 and s_max > s_min else 0.0
    diagram = []
    for i in range(payoff_points):
        s = s_min + i * step
        diagram.append(
            {
                "underlying": round(s, 2),
                "payoff": round(_payoff_for_kind(strategy_kind, params, s), 2),
            }
        )
    return {
        "expected_value": round(expected, 4),
        "probability_of_profit": round(prob_profit, 4),
        "max_loss": round(max_loss, 4),
        "max_gain": round(max_gain, 4),
        "payoff_diagram": diagram,
    }


def distribution_from_forecast(
    mean: float,
    std: float | None = None,
    *,
    num_bins: int = 31,
    num_std: float = 2.0,
) -> list[tuple[float, float]]:
    """
    Build a discrete (approximate) normal distribution from point forecast and optional std.

    Used when we only have a point forecast (e.g. from ARIMA); optionally use
    historical volatility or ARIMA prediction interval for std. If std is None,
    use a single point (mean, 1.0).
    """
    if std is None or std <= 0:
        return [(mean, 1.0)]
    import math
    low = mean - num_std * std
    high = mean + num_std * std
    step = (high - low) / (num_bins - 1) if num_bins > 1 else 0.0
    total = 0.0
    points: list[tuple[float, float]] = []
    for i in range(num_bins):
        s = low + i * step
        # Normal PDF (unnormalized) then we normalize
        z = (s - mean) / std if std else 0.0
        p = math.exp(-0.5 * z * z)
        points.append((s, p))
        total += p
    if total <= 0:
        return [(mean, 1.0)]
    return [(s, p / total) for s, p in points]
