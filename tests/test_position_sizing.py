"""Tests for position sizing (Kelly Criterion) and break-even modules."""

import pytest
from fastapi.testclient import TestClient

from risk.position_sizing import (
    kelly_fraction,
    half_kelly_fraction,
    fixed_risk_size,
    max_contracts,
)
from strategy_engine.breakeven import compute_breakeven_prices
from strategy_engine.strategies import StrategyKind


# ── Unit tests: risk/position_sizing.py ─────────────────────────────────────

class TestKellyFraction:
    def test_positive_edge(self):
        # 55% win rate, win/loss ratio 1.67 → positive Kelly
        result = kelly_fraction(0.55, 500, 300)
        assert result is not None
        assert 0 < result < 1

    def test_negative_edge_clamped_to_zero(self):
        # 30% win rate, equal win/loss → negative Kelly → clamped to 0
        result = kelly_fraction(0.30, 100, 100)
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_invalid_win_rate_zero(self):
        assert kelly_fraction(0.0, 100, 100) is None

    def test_invalid_win_rate_one(self):
        assert kelly_fraction(1.0, 100, 100) is None

    def test_invalid_avg_loss_zero(self):
        assert kelly_fraction(0.55, 100, 0) is None

    def test_invalid_avg_win_zero(self):
        assert kelly_fraction(0.55, 0, 100) is None

    def test_result_never_exceeds_one(self):
        result = kelly_fraction(0.99, 10000, 1)
        assert result is not None
        assert result <= 1.0

    def test_symmetric_50_50_zero_edge(self):
        # 50/50 with equal win/loss = no edge = 0
        result = kelly_fraction(0.50, 100, 100)
        assert result == pytest.approx(0.0, abs=1e-9)


class TestHalfKelly:
    def test_half_of_full_kelly(self):
        full = kelly_fraction(0.55, 500, 300)
        half = half_kelly_fraction(0.55, 500, 300)
        assert full is not None and half is not None
        assert half == pytest.approx(full / 2.0, rel=1e-6)

    def test_returns_none_for_invalid_inputs(self):
        assert half_kelly_fraction(0.0, 100, 100) is None


class TestFixedRiskSize:
    def test_basic_calculation(self):
        units = fixed_risk_size(10000, 1.0, 200)
        assert units == pytest.approx(0.5, rel=1e-6)

    def test_invalid_capital(self):
        assert fixed_risk_size(0, 1.0, 100) is None

    def test_invalid_loss_per_unit(self):
        assert fixed_risk_size(10000, 1.0, 0) is None

    def test_larger_risk_pct_gives_more_units(self):
        units1 = fixed_risk_size(10000, 1.0, 100)
        units2 = fixed_risk_size(10000, 2.0, 100)
        assert units2 == pytest.approx(units1 * 2, rel=1e-6)


class TestMaxContracts:
    def test_basic_calculation(self):
        # $10,000, 1% risk = $100 budget; $2 debit × 100 = $200/contract → 0 contracts
        result = max_contracts(10000, 1.0, 2.0, 100)
        assert result == 0

    def test_sufficient_budget(self):
        # $10,000, 5% risk = $500 budget; $2 debit × 100 = $200/contract → 2 contracts
        result = max_contracts(10000, 5.0, 2.0, 100)
        assert result == 2

    def test_invalid_capital(self):
        assert max_contracts(0, 1.0, 2.0, 100) is None

    def test_never_negative(self):
        result = max_contracts(100, 0.1, 1000, 100)
        assert result is not None
        assert result >= 0


# ── Unit tests: strategy_engine/breakeven.py ────────────────────────────────

class TestComputeBreakevenPrices:
    def test_straddle_two_breakevens(self):
        params = {"strike": 100.0}
        bes = compute_breakeven_prices(StrategyKind.STRADDLE, params, premium_paid=5.0)
        assert len(bes) == 2
        assert bes[0] == pytest.approx(95.0)
        assert bes[1] == pytest.approx(105.0)

    def test_straddle_no_premium_returns_empty(self):
        params = {"strike": 100.0}
        bes = compute_breakeven_prices(StrategyKind.STRADDLE, params, premium_paid=None)
        assert bes == []

    def test_bull_call_spread_one_breakeven(self):
        params = {"long_strike": 98.0, "short_strike": 102.0}
        bes = compute_breakeven_prices(StrategyKind.VERTICAL_SPREAD_CALL, params, premium_paid=2.0)
        assert len(bes) == 1
        assert bes[0] == pytest.approx(100.0)

    def test_bear_put_spread_one_breakeven(self):
        params = {"long_strike": 102.0, "short_strike": 98.0}
        bes = compute_breakeven_prices(StrategyKind.VERTICAL_SPREAD_PUT, params, premium_paid=2.0)
        assert len(bes) == 1
        assert bes[0] == pytest.approx(100.0)

    def test_iron_condor_two_breakevens(self):
        params = {
            "put_long": 90.0, "put_short": 95.0,
            "call_short": 105.0, "call_long": 110.0,
        }
        # Credit received = $2 → premium_paid = -2
        bes = compute_breakeven_prices(StrategyKind.IRON_CONDOR, params, premium_paid=-2.0)
        assert len(bes) == 2
        assert bes[0] == pytest.approx(93.0)   # put_short - credit = 95 - 2
        assert bes[1] == pytest.approx(107.0)  # call_short + credit = 105 + 2

    def test_calendar_call_two_breakevens(self):
        params = {"strike": 100.0, "net_debit": 3.0}
        bes = compute_breakeven_prices(StrategyKind.CALENDAR_SPREAD_CALL, params, premium_paid=3.0)
        assert len(bes) == 2

    def test_result_is_sorted(self):
        params = {"strike": 100.0}
        bes = compute_breakeven_prices(StrategyKind.STRADDLE, params, premium_paid=8.0)
        assert bes == sorted(bes)

    def test_negative_breakevens_excluded(self):
        # Large premium on very low strike could produce negative BE
        params = {"long_strike": 5.0, "short_strike": 10.0}
        bes = compute_breakeven_prices(StrategyKind.VERTICAL_SPREAD_CALL, params, premium_paid=10.0)
        assert all(p > 0 for p in bes)


# ── API integration tests ────────────────────────────────────────────────────

@pytest.fixture
def client(fresh_storage_file):
    """FastAPI test client with fresh DB and auth override."""
    from api.main import app
    from api import auth_utils
    from storage.session import create_all_tables

    app.dependency_overrides[auth_utils.get_current_user] = auth_utils.get_default_user
    try:
        with TestClient(app) as c:
            create_all_tables()
            yield c
    finally:
        app.dependency_overrides.pop(auth_utils.get_current_user, None)


def test_position_size_endpoint(client):
    r = client.post(
        "/risk/position-size",
        json={
            "capital": 10000,
            "win_rate": 0.55,
            "avg_win": 500,
            "avg_loss": 300,
            "max_risk_pct": 1.0,
            "max_loss_per_contract": 2.0,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["kelly_fraction"] is not None
    assert data["half_kelly_fraction"] is not None
    assert data["fixed_risk_dollar"] == pytest.approx(100.0)


def test_breakeven_endpoint_straddle(client):
    r = client.post(
        "/risk/breakeven",
        json={"strategy_type": "straddle", "strike": 100.0, "premium_paid": 5.0},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert len(data["breakeven_prices"]) == 2


def test_breakeven_endpoint_invalid_strategy(client):
    r = client.post(
        "/risk/breakeven",
        json={"strategy_type": "invalid_type", "premium_paid": 5.0},
    )
    assert r.status_code == 200
    assert r.json()["success"] is False


def test_strategy_evaluate_with_premium_returns_breakeven(client):
    r = client.post(
        "/strategy-engine/evaluate",
        json={
            "strategy_type": "straddle",
            "forecast_mean": 100.0,
            "forecast_std": 5.0,
            "strike": 100.0,
            "premium_paid": 4.0,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "breakeven_prices" in data
    assert len(data["breakeven_prices"]) == 2
    assert data["breakeven_prices"][0] == pytest.approx(96.0)
    assert data["breakeven_prices"][1] == pytest.approx(104.0)


def test_strategy_evaluate_without_premium_no_breakeven(client):
    r = client.post(
        "/strategy-engine/evaluate",
        json={
            "strategy_type": "straddle",
            "forecast_mean": 100.0,
            "strike": 100.0,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["breakeven_prices"] == []
