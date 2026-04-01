"""
Forecast evaluation: directional accuracy, RMSE, and backtest returns.

Uses the same price/return data as the backtesting engine so that forecast
quality can be compared to actual backtest performance.
"""

import pandas as pd


def evaluate_forecast(
    actual: pd.Series,
    predicted: pd.Series,
    *,
    direction_from_actual: pd.Series | None = None,
    direction_from_pred: pd.Series | None = None,
) -> dict[str, float]:
    """
    Compute directional accuracy and RMSE between actual and predicted series.

    Args:
        actual: Realized values (same length as predicted, or longer; alignment by index).
        predicted: Predicted values.
        direction_from_actual: Optional precomputed direction ("up"/"down"/"flat") per step.
        direction_from_pred: Optional precomputed predicted direction per step.

    Returns:
        Dict with keys: directional_accuracy (0-1), rmse, mae, n_observations.
    """
    common = actual.index.intersection(predicted.index)
    if len(common) == 0:
        return {
            "directional_accuracy": 0.0,
            "rmse": 0.0,
            "mae": 0.0,
            "n_observations": 0,
        }
    a = actual.reindex(common).dropna()
    p = predicted.reindex(common).dropna()
    again = a.index.intersection(p.index)
    a = a.reindex(again).dropna()
    p = p.reindex(again).dropna()
    if a.empty or p.empty:
        return {
            "directional_accuracy": 0.0,
            "rmse": 0.0,
            "mae": 0.0,
            "n_observations": 0,
        }
    n = len(a)
    diff = a - p
    rmse = (diff ** 2).mean() ** 0.5
    mae = diff.abs().mean()

    if direction_from_actual is not None and direction_from_pred is not None:
        d_act = direction_from_actual.reindex(again).dropna()
        d_pr = direction_from_pred.reindex(again).dropna()
        idx = d_act.index.intersection(d_pr.index)
        matches = (d_act.reindex(idx) == d_pr.reindex(idx)).sum()
        total = len(idx)
        dir_acc = (matches / total) if total else 0.0
    else:
        # Infer direction from change: up if current > previous, down if <, else flat
        diff_actual = a.diff()
        dir_actual = pd.Series("flat", index=a.index, dtype=object)
        dir_actual.loc[diff_actual > 0] = "up"
        dir_actual.loc[diff_actual < 0] = "down"
        diff_pred = p.diff()
        dir_pred = pd.Series("flat", index=p.index, dtype=object)
        dir_pred.loc[diff_pred > 0] = "up"
        dir_pred.loc[diff_pred < 0] = "down"
        matches = (dir_actual == dir_pred).sum()
        total = len(dir_actual)
        dir_acc = (matches / total) if total else 0.0

    return {
        "directional_accuracy": float(dir_acc),
        "rmse": float(rmse),
        "mae": float(mae),
        "n_observations": n,
    }


def backtest_returns_from_signals(
    prices: pd.Series,
    signals: pd.Series,
    *,
    signal_up: str = "up",
    signal_down: str = "down",
) -> dict[str, float]:
    """
    Compute simple backtest returns from directional signals (e.g. from a forecaster).

    Rule: long when signal is up, short when down, flat otherwise. One period hold.
    Uses the same price series semantics as the backtesting engine (e.g. close).

    Args:
        prices: Close price (or return) series with datetime index.
        signals: Series of "up", "down", "flat" aligned to prices.
        signal_up: Value meaning long.
        signal_down: Value meaning short.

    Returns:
        Dict with total_return, n_trades, win_rate (fraction of profitable trades).
    """
    common = prices.index.intersection(signals.index)
    if len(common) < 2:
        return {"total_return": 0.0, "n_trades": 0, "win_rate": 0.0}
    p = prices.reindex(common).ffill().dropna()
    s = signals.reindex(common).ffill().dropna()
    idx = p.index.intersection(s.index)
    p = p.reindex(idx).ffill()
    s = s.reindex(idx).ffill()
    ret = p.pct_change()
    position = s.map(lambda x: 1.0 if x == signal_up else (-1.0 if x == signal_down else 0.0))
    strategy_ret = (position.shift(1) * ret).dropna()
    total_return = float((1 + strategy_ret).prod() - 1.0) if len(strategy_ret) else 0.0
    n_trades = (position.diff().fillna(0).abs() > 0).sum()
    wins = (strategy_ret > 0).sum()
    win_rate = (wins / len(strategy_ret)) if len(strategy_ret) else 0.0
    return {
        "total_return": total_return,
        "n_trades": int(n_trades),
        "win_rate": float(win_rate),
    }
