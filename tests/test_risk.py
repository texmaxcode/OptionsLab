"""Tests for risk metrics."""

from risk import max_drawdown, volatility_annualized, var_historical


def test_max_drawdown_empty() -> None:
    assert max_drawdown([]) == 0.0


def test_max_drawdown_no_decline() -> None:
    assert max_drawdown([100.0, 101.0, 102.0]) == 0.0


def test_max_drawdown_simple() -> None:
    # Peak 100, trough 80 -> 20% dd
    assert max_drawdown([100.0, 90.0, 80.0, 85.0]) == 0.2


def test_volatility_annualized_empty() -> None:
    assert volatility_annualized([]) == 0.0


def test_volatility_annualized_single_return() -> None:
    """Single return has no variance; returns 0."""
    assert volatility_annualized([0.01]) == 0.0


def test_volatility_annualized() -> None:
    # Constant returns -> 0 vol
    assert volatility_annualized([0.01, 0.01, 0.01]) == 0.0
    # Non-zero variance
    vol = volatility_annualized([0.01, -0.01, 0.02])
    assert vol > 0


def test_var_historical_empty() -> None:
    assert var_historical([]) == 0.0


def test_var_historical_95() -> None:
    # 20 returns: 19 positive, 1 at -0.05. 95% VaR = 5% quantile of returns -> worst 5% is -0.05
    returns = [0.01] * 19 + [-0.05]
    assert var_historical(returns, alpha=0.95) == 0.05


def test_var_historical_all_positive() -> None:
    assert var_historical([0.01, 0.02, 0.01], alpha=0.95) == 0.0
