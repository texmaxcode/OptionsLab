"""
Forecast-based options strategy evaluation API.

Evaluates strategies (vertical spreads, straddle, iron condor, calendar spreads)
using a forecast distribution. Returns expected value, risk metrics, and payoff
diagram. Optional comparison to historical backtest when symbol/dates provided.
See docs/STRATEGY_ENGINE.md.
"""

from typing import Any

from fastapi import APIRouter, Depends

from api import auth_utils
from api.schemas import (
    PayoffPoint,
    StrategyDiscoverRequest,
    StrategyDiscoverResponse,
    StrategyDiscoverResult,
    StrategyEvaluateRequest,
    StrategyEvaluateResponse,
)
from models.sql_models import UserModel
from risk import max_drawdown
from strategy_engine import compute_breakeven_prices, expected_payoff_and_risk
from strategy_engine.expected_value import distribution_from_forecast
from strategy_engine.strategies import StrategyKind

router = APIRouter(prefix="/strategy-engine", tags=["strategy-engine"])


def _params_for_request(body: StrategyEvaluateRequest) -> dict[str, Any]:
    """Build strategy params dict from request body."""
    if body.strategy_type in ("vertical_spread_call", "vertical_spread_put"):
        if body.long_strike is None or body.short_strike is None:
            raise ValueError("long_strike and short_strike required for vertical spread")
        return {"long_strike": body.long_strike, "short_strike": body.short_strike}
    if body.strategy_type == "straddle":
        if body.strike is None:
            raise ValueError("strike required for straddle")
        return {"strike": body.strike}
    if body.strategy_type == "iron_condor":
        if (
            body.put_long is None
            or body.put_short is None
            or body.call_short is None
            or body.call_long is None
        ):
            raise ValueError(
                "put_long, put_short, call_short, call_long required for iron condor"
            )
        return {
            "put_long": body.put_long,
            "put_short": body.put_short,
            "call_short": body.call_short,
            "call_long": body.call_long,
        }
    if body.strategy_type in ("calendar_spread_call", "calendar_spread_put"):
        if body.strike is None:
            raise ValueError("strike required for calendar spread")
        net_debit = body.net_debit if body.net_debit is not None else 0.0
        return {"strike": body.strike, "net_debit": net_debit}
    raise ValueError(f"Unknown strategy_type: {body.strategy_type}")


def _strategy_kind(s: str) -> StrategyKind:
    """Parse strategy type string to StrategyKind."""
    try:
        return StrategyKind(s)
    except ValueError:
        raise ValueError(
            f"strategy_type must be one of: {[k.value for k in StrategyKind]}"
        ) from None


@router.post("/evaluate", response_model=StrategyEvaluateResponse)
async def evaluate_strategy(
    body: StrategyEvaluateRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """
    Evaluate an options strategy using a forecast distribution.

    Provide forecast_mean (and optionally forecast_std for uncertainty).
    Strategy params depend on strategy_type. Returns expected value,
    probability of profit, max loss/gain, and payoff diagram for UI.
    """
    try:
        kind = _strategy_kind(body.strategy_type)
        params = _params_for_request(body)
    except ValueError as e:
        return StrategyEvaluateResponse(
            success=False,
            strategy_type=body.strategy_type,
            expected_value=0.0,
            probability_of_profit=0.0,
            max_loss=0.0,
            max_gain=0.0,
            error=str(e),
            historical_backtest_return=None,
            historical_backtest_drawdown=None,
            historical_backtest_error=None,
        )
    try:
        dist = distribution_from_forecast(
            body.forecast_mean,
            body.forecast_std,
            num_bins=31,
            num_std=2.0,
        )
        result = expected_payoff_and_risk(kind, params, dist)
        backtest_return: float | None = None
        backtest_drawdown: float | None = None
        backtest_error: str | None = None
        if (
            body.include_backtest
            and body.symbol
            and body.from_date
            and body.to_date
        ):
            try:
                from api.services.run_backtest import run_backtest
                bt_result = run_backtest(
                    strategy="sma_crossover",
                    underlying=body.symbol,
                    from_date=body.from_date,
                    to_date=body.to_date,
                )
                if bt_result.get("success") and bt_result.get("start_value"):
                    sv = bt_result["start_value"]
                    ev = bt_result.get("end_value") or sv
                    backtest_return = (ev - sv) / sv if sv else None
                    equity = bt_result.get("equity_curve") or []
                    if equity:
                        curve = [p["value"] for p in equity]
                        backtest_drawdown = max_drawdown(curve)
                else:
                    backtest_error = bt_result.get("error") or "Backtest failed"
            except Exception as e:
                backtest_error = str(e)
        # Compute break-even prices when premium is provided
        be_prices = compute_breakeven_prices(kind, params, body.premium_paid)

        return StrategyEvaluateResponse(
            success=True,
            strategy_type=body.strategy_type,
            expected_value=result["expected_value"],
            probability_of_profit=result["probability_of_profit"],
            max_loss=result["max_loss"],
            max_gain=result["max_gain"],
            payoff_diagram=[PayoffPoint(**p) for p in result["payoff_diagram"]],
            breakeven_prices=be_prices,
            error=None,
            historical_backtest_return=backtest_return,
            historical_backtest_drawdown=backtest_drawdown,
            historical_backtest_error=backtest_error,
        )
    except Exception as e:
        return StrategyEvaluateResponse(
            success=False,
            strategy_type=body.strategy_type,
            expected_value=0.0,
            probability_of_profit=0.0,
            max_loss=0.0,
            max_gain=0.0,
            error=str(e),
            historical_backtest_return=None,
            historical_backtest_drawdown=None,
            historical_backtest_error=None,
        )


@router.post("/discover", response_model=StrategyDiscoverResponse)
async def discover_strategies(
    body: StrategyDiscoverRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """
    Automatically rank all strategy types for a symbol/period.

    Runs a forecast for the given symbol and date range, then evaluates every
    supported strategy type with auto-generated parameters (based on the forecast
    mean and a configurable spread width). Returns results sorted by expected
    value descending so the highest-EV strategy is ranked first.
    """
    from features import load_underlying_series, build_ohlcv_features
    from forecasting import ARIMAForecaster, GBForecaster
    from api.utils import parse_iso_date

    from_dt = parse_iso_date(body.from_date)
    to_dt = parse_iso_date(body.to_date)
    if from_dt is None or to_dt is None:
        return StrategyDiscoverResponse(
            success=False, symbol=body.symbol, error="Invalid date format. Use YYYY-MM-DD."
        )

    try:
        df = load_underlying_series(body.symbol, from_date=from_dt, to_date=to_dt)
    except Exception as e:
        return StrategyDiscoverResponse(
            success=False, symbol=body.symbol, error=f"Failed to load data: {e}"
        )

    if df.empty or len(df) < 10:
        return StrategyDiscoverResponse(
            success=False,
            symbol=body.symbol,
            error="Insufficient data. Sync data for this symbol and range.",
        )

    try:
        feat = build_ohlcv_features(df, drop_na=True)
        if feat.empty:
            return StrategyDiscoverResponse(
                success=False, symbol=body.symbol, error="Feature build produced no rows."
            )
        if body.model == "gb":
            forecaster = GBForecaster(n_lag=5).fit(feat["close"])
        else:
            forecaster = ARIMAForecaster(order=(1, 0, 0)).fit(feat["close"])
        pred = forecaster.predict(horizon=body.horizon)
        forecast_mean = float(pred.iloc[-1])
        forecast_direction = forecaster.predict_direction(horizon=body.horizon)
        train_std = feat["close"].pct_change().dropna().std()
        forecast_std = float(train_std * (body.horizon ** 0.5)) if train_std and body.horizon else None
    except Exception as e:
        return StrategyDiscoverResponse(
            success=False, symbol=body.symbol, error=f"Forecast failed: {e}"
        )

    from strategy_engine.expected_value import distribution_from_forecast

    dist = distribution_from_forecast(forecast_mean, forecast_std)
    w = body.spread_width_pct
    m = forecast_mean

    # Auto-generate params for each strategy type based on forecast mean
    candidates: list[tuple[StrategyKind, dict]] = [
        (StrategyKind.VERTICAL_SPREAD_CALL, {"long_strike": m * (1 - w), "short_strike": m * (1 + w)}),
        (StrategyKind.VERTICAL_SPREAD_PUT, {"long_strike": m * (1 + w), "short_strike": m * (1 - w)}),
        (StrategyKind.STRADDLE, {"strike": m}),
        (
            StrategyKind.IRON_CONDOR,
            {
                "put_long": m * (1 - 3 * w),
                "put_short": m * (1 - w),
                "call_short": m * (1 + w),
                "call_long": m * (1 + 3 * w),
            },
        ),
        (StrategyKind.CALENDAR_SPREAD_CALL, {"strike": m, "net_debit": m * w * 0.5}),
        (StrategyKind.CALENDAR_SPREAD_PUT, {"strike": m, "net_debit": m * w * 0.5}),
    ]

    raw_results = []
    for kind, params in candidates:
        try:
            res = expected_payoff_and_risk(kind, params, dist)
            raw_results.append(
                {
                    "strategy_type": kind.value,
                    "params": params,
                    "expected_value": res["expected_value"],
                    "probability_of_profit": res["probability_of_profit"],
                    "max_loss": res["max_loss"],
                    "max_gain": res["max_gain"],
                }
            )
        except Exception:
            continue

    raw_results.sort(key=lambda r: r["expected_value"], reverse=True)
    ranked = [
        StrategyDiscoverResult(rank=i + 1, **r)
        for i, r in enumerate(raw_results)
    ]

    return StrategyDiscoverResponse(
        success=True,
        symbol=body.symbol,
        forecast_direction=forecast_direction,
        forecast_mean=forecast_mean,
        forecast_std=forecast_std,
        results=ranked,
    )
