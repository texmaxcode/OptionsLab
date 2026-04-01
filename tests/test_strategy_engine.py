"""Tests for the forecast-based strategy engine."""

import pytest

from strategy_engine.payoff import (
    payoff_vertical_spread_call,
    payoff_vertical_spread_put,
    payoff_straddle,
    payoff_iron_condor,
    payoff_calendar_call,
    payoff_calendar_put,
)
from strategy_engine.expected_value import (
    expected_payoff_and_risk,
    distribution_from_forecast,
)
from strategy_engine.strategies import StrategyKind, get_strategy_payoff_fn


def test_vertical_spread_call() -> None:
    # Long 100, short 110. At 105: long +5, short 0 -> 5
    assert payoff_vertical_spread_call(105.0, 100.0, 110.0) == 5.0
    assert payoff_vertical_spread_call(115.0, 100.0, 110.0) == 10.0  # cap
    assert payoff_vertical_spread_call(95.0, 100.0, 110.0) == 0.0


def test_vertical_spread_put() -> None:
    # Long 110, short 100. At 105: long 5, short 0 -> 5
    assert payoff_vertical_spread_put(105.0, 110.0, 100.0) == 5.0
    assert payoff_vertical_spread_put(90.0, 110.0, 100.0) == 10.0
    assert payoff_vertical_spread_put(115.0, 110.0, 100.0) == 0.0


def test_vertical_spread_put_invalid_strikes() -> None:
    with pytest.raises(ValueError, match="long_strike > short_strike"):
        payoff_vertical_spread_put(100.0, 100.0, 110.0)


def test_calendar_call() -> None:
    # At 105, long call at 100 pays 5; net_debit 1 -> payoff 4
    assert payoff_calendar_call(105.0, 100.0, 1.0) == 4.0
    assert payoff_calendar_call(95.0, 100.0, 0.5) == -0.5


def test_calendar_put() -> None:
    assert payoff_calendar_put(95.0, 100.0, 1.0) == 4.0
    assert payoff_calendar_put(105.0, 100.0, 0.0) == 0.0


def test_get_strategy_payoff_fn_calendar() -> None:
    assert get_strategy_payoff_fn(StrategyKind.CALENDAR_SPREAD_CALL)(105.0, 100.0, 0.0) == 5.0
    assert get_strategy_payoff_fn(StrategyKind.CALENDAR_SPREAD_PUT)(95.0, 100.0, 0.0) == 5.0


def test_straddle() -> None:
    assert payoff_straddle(100.0, 100.0) == 0.0
    assert payoff_straddle(110.0, 100.0) == 10.0
    assert payoff_straddle(90.0, 100.0) == 10.0


def test_iron_condor() -> None:
    # put_long 90, put_short 95, call_short 105, call_long 110
    # At 100: all options OTM -> 0
    assert payoff_iron_condor(100.0, 95.0, 90.0, 105.0, 110.0) == 0.0


def test_distribution_from_forecast_single_point() -> None:
    dist = distribution_from_forecast(100.0, None)
    assert dist == [(100.0, 1.0)]


def test_distribution_from_forecast_normal() -> None:
    dist = distribution_from_forecast(100.0, 5.0, num_bins=5)
    assert len(dist) == 5
    total = sum(p for _, p in dist)
    assert abs(total - 1.0) < 0.01


def test_expected_payoff_and_risk_straddle() -> None:
    dist = [(100.0, 0.5), (110.0, 0.5)]
    res = expected_payoff_and_risk(
        StrategyKind.STRADDLE,
        {"strike": 100.0},
        dist,
        payoff_points=5,
    )
    assert "expected_value" in res
    assert "probability_of_profit" in res
    assert "max_loss" in res
    assert "max_gain" in res
    assert len(res["payoff_diagram"]) == 5


def test_get_strategy_payoff_fn() -> None:
    fn = get_strategy_payoff_fn(StrategyKind.STRADDLE)
    assert fn(110.0, 100.0) == 10.0
    fn_ic = get_strategy_payoff_fn(StrategyKind.IRON_CONDOR)
    assert fn_ic(100.0, 95.0, 90.0, 105.0, 110.0) == 0.0


# ---------------------------------------------------------------------------
# Strategy discovery helpers (unit-level, no DB)
# ---------------------------------------------------------------------------

def test_expected_payoff_all_strategy_kinds() -> None:
    """All StrategyKind values can be evaluated without raising."""
    dist = distribution_from_forecast(100.0, 5.0, num_bins=11)
    m = 100.0
    w = 0.02
    params_by_kind = {
        StrategyKind.VERTICAL_SPREAD_CALL: {"long_strike": m * (1 - w), "short_strike": m * (1 + w)},
        StrategyKind.VERTICAL_SPREAD_PUT: {"long_strike": m * (1 + w), "short_strike": m * (1 - w)},
        StrategyKind.STRADDLE: {"strike": m},
        StrategyKind.IRON_CONDOR: {
            "put_long": m * (1 - 3 * w),
            "put_short": m * (1 - w),
            "call_short": m * (1 + w),
            "call_long": m * (1 + 3 * w),
        },
        StrategyKind.CALENDAR_SPREAD_CALL: {"strike": m, "net_debit": m * w * 0.5},
        StrategyKind.CALENDAR_SPREAD_PUT: {"strike": m, "net_debit": m * w * 0.5},
    }
    for kind, params in params_by_kind.items():
        res = expected_payoff_and_risk(kind, params, dist)
        assert "expected_value" in res, f"Missing expected_value for {kind}"
        assert isinstance(res["expected_value"], float), f"Wrong type for {kind}"


def test_distribution_probabilities_sum_to_one() -> None:
    for std in (None, 2.0, 10.0):
        dist = distribution_from_forecast(100.0, std, num_bins=21)
        total = sum(p for _, p in dist)
        assert abs(total - 1.0) < 0.01, f"Probabilities don't sum to 1 for std={std}"


def test_distribution_prices_around_mean() -> None:
    mean = 150.0
    dist = distribution_from_forecast(mean, 10.0, num_bins=11)
    prices = [p for p, _ in dist]
    assert min(prices) < mean < max(prices)


def test_expected_payoff_straddle_symmetric() -> None:
    """A symmetric distribution around the strike gives a non-negative EV for straddles."""
    dist = [(90.0, 0.5), (110.0, 0.5)]
    res = expected_payoff_and_risk(StrategyKind.STRADDLE, {"strike": 100.0}, dist)
    assert res["expected_value"] == pytest.approx(10.0)
    assert res["probability_of_profit"] == pytest.approx(1.0)


def test_expected_payoff_returns_payoff_diagram() -> None:
    dist = distribution_from_forecast(100.0, 5.0, num_bins=5)
    res = expected_payoff_and_risk(
        StrategyKind.IRON_CONDOR,
        {"put_long": 88.0, "put_short": 93.0, "call_short": 107.0, "call_long": 112.0},
        dist,
        payoff_points=10,
    )
    assert len(res["payoff_diagram"]) == 10
    for point in res["payoff_diagram"]:
        assert "underlying" in point
        assert "payoff" in point


def test_payoff_diagram_uses_strike_range_when_distribution_is_single_point() -> None:
    """Degenerate forecast (no std) is one price mass; diagram must still span the strike."""
    dist = distribution_from_forecast(100.0, None)
    assert len(dist) == 1
    res = expected_payoff_and_risk(
        StrategyKind.STRADDLE,
        {"strike": 100.0},
        dist,
        payoff_points=21,
    )
    unders = [p["underlying"] for p in res["payoff_diagram"]]
    assert min(unders) < 100.0 < max(unders)
    payoffs = [p["payoff"] for p in res["payoff_diagram"]]
    assert max(payoffs) > min(payoffs)
