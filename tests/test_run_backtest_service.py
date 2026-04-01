"""Tests for api.services.run_backtest: run_backtest(), _compute_drawdown_curve."""

import os
from datetime import datetime, timedelta

os.environ.setdefault("TRADING_DATABASE_URL", "sqlite:///:memory:")

from api.services.run_backtest import (
    run_backtest,
    _compute_drawdown_curve,
)
from storage import session_scope, UnderlyingBarRepository


def test_compute_drawdown_curve_empty() -> None:
    """_compute_drawdown_curve with empty list returns empty list."""
    assert _compute_drawdown_curve([]) == []


def test_compute_drawdown_curve_single_point() -> None:
    """_compute_drawdown_curve with one point has zero drawdown at peak."""
    curve = [{"date": "2024-01-01", "value": 100.0}]
    out = _compute_drawdown_curve(curve)
    assert len(out) == 1
    assert out[0]["date"] == "2024-01-01"
    assert out[0]["drawdown"] == 0.0


def test_compute_drawdown_curve_drawdown() -> None:
    """_compute_drawdown_curve computes drawdown from peak."""
    curve = [
        {"date": "2024-01-01", "value": 100.0},
        {"date": "2024-01-02", "value": 90.0},
        {"date": "2024-01-03", "value": 95.0},
    ]
    out = _compute_drawdown_curve(curve)
    assert len(out) == 3
    assert out[0]["drawdown"] == 0.0
    assert out[1]["drawdown"] == 10.0  # (100-90)/100
    assert out[2]["drawdown"] == 5.0   # (100-95)/100


def test_run_backtest_unknown_strategy() -> None:
    """Unknown strategy returns success=False and error message."""
    result = run_backtest("unknown", "AAPL", from_date="2024-01-01", to_date="2024-01-31")
    assert result["success"] is False
    assert "Unknown strategy" in result["error"]


def test_run_backtest_equity_missing_dates() -> None:
    """Equity strategy without from_date/to_date returns error."""
    result = run_backtest("sma_crossover", "AAPL")
    assert result["success"] is False
    assert "from_date" in result["error"] or "to_date" in result["error"]


def test_run_backtest_equity_no_bars(fresh_storage) -> None:
    """Equity strategy with no bars in DB returns error."""
    result = run_backtest(
        "sma_crossover", "AAPL",
        from_date="2024-01-01", to_date="2024-01-31",
    )
    assert result["success"] is False
    assert "No underlying bars" in result["error"]


def test_run_backtest_equity_success_with_chart_data(fresh_storage) -> None:
    """Equity strategy with bars runs and returns chart_data (equity_curve, drawdown_curve)."""
    with session_scope() as session:
        repo = UnderlyingBarRepository(session)
        # SMA crossover uses slow_period=50, so need at least 50+ bars
        for i in range(60):
            dt = datetime(2024, 1, 1) + timedelta(days=i)
            repo.upsert_bar("AAPL", dt, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1_000_000)
        session.commit()

    result = run_backtest(
        "sma_crossover", "AAPL",
        from_date="2024-01-01", to_date="2024-03-01",
    )
    assert result["success"] is True
    assert result.get("start_value") is not None
    assert result.get("end_value") is not None
    assert "chart_data" in result
    chart = result["chart_data"]
    assert "equity_curve" in chart
    assert "drawdown_curve" in chart
    # equity_curve and drawdown_curve populated by _extract_chart_data
    if chart.get("equity_curve"):
        assert len(chart["drawdown_curve"]) == len(chart["equity_curve"])


def test_run_backtest_options_no_contract(fresh_storage) -> None:
    """Options strategy with no contract_id/symbol/first_contract returns error."""
    result = run_backtest("single_leg", "AAPL", from_date="2024-01-01", to_date="2024-01-31")
    assert result["success"] is False
    assert "No contract" in result["error"] or "contract" in result["error"].lower()


def test_run_backtest_options_first_contract_no_contracts_in_db(fresh_storage) -> None:
    """Options strategy with first_contract=True but no contracts returns error."""
    result = run_backtest(
        "single_leg", "AAPL",
        from_date="2024-01-01", to_date="2024-01-31",
        first_contract=True,
    )
    assert result["success"] is False
    assert "No options contracts" in result["error"]


def test_run_backtest_options_no_bars(fresh_storage) -> None:
    """Options strategy with contract but no bars returns error."""
    from models.sql_models import OptionsContractModel
    from storage import session_scope
    with session_scope() as session:
        contract = OptionsContractModel(
            underlying_symbol="AAPL",
            expiration=datetime(2024, 2, 16),
            strike=180.0,
            option_type="call",
            contract_symbol="AAPL240216C00180000",
        )
        session.add(contract)
        session.commit()
        session.refresh(contract)
        cid = contract.id
    result = run_backtest(
        "single_leg", "AAPL",
        from_date="2024-01-01", to_date="2024-01-31",
        contract_id=cid,
    )
    assert result["success"] is False
    assert "No options bars" in result["error"]
