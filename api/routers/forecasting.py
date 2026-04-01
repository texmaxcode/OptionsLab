"""
Time-series forecasting API.

Uses the same market data as the backtesting engine so forecasts and backtests
are comparable. See docs/FORECASTING.md and docs/DATA_AND_FEATURES.md.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from api import auth_utils
from api.utils import parse_iso_date
from api.schemas import (
    EvaluateForecastRequest,
    EvaluateForecastResponse,
    ForecastRequest,
    ForecastResponse,
    ForecastPoint,
)
from features import load_underlying_series, build_ohlcv_features, load_macro_features, join_macro_features
from forecasting import (
    ARIMAForecaster,
    GBForecaster,
    evaluate_forecast,
    backtest_returns_from_signals,
)
from forecasting.registry import register_forecast_run, list_forecast_runs
from models.sql_models import UserModel

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("/runs")
async def list_runs(
    symbol: str | None = None,
    model_type: str | None = None,
    limit: int = 50,
    current_user: UserModel = Depends(auth_utils.get_current_user),
) -> list[dict]:
    """
    List registered forecast runs (model registry). Optional filters: symbol, model_type.
    """
    return list_forecast_runs(symbol=symbol, model_type=model_type, limit=limit)


@router.post("/run", response_model=ForecastResponse)
async def run_forecast(
    body: ForecastRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """
    Run a time-series forecast for the given symbol and date range.

    Uses the same underlying data as backtests (storage). Result includes
    direction (up/down/flat) and point forecast for the next horizon steps.
    """
    from_dt = parse_iso_date(body.from_date)
    to_dt = parse_iso_date(body.to_date)
    if from_dt is None or to_dt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD.",
        )

    if body.model not in ("arima", "gb"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="model must be 'arima' or 'gb'.",
        ) from None

    try:
        df = load_underlying_series(body.symbol, from_date=from_dt, to_date=to_dt)
    except Exception as e:
        return ForecastResponse(
            success=False,
            symbol=body.symbol,
            from_date=body.from_date,
            to_date=body.to_date,
            horizon=body.horizon,
            model=body.model,
            direction="flat",
            error=f"Failed to load data: {e}",
        )

    if df.empty or len(df) < 10:
        return ForecastResponse(
            success=False,
            symbol=body.symbol,
            from_date=body.from_date,
            to_date=body.to_date,
            horizon=body.horizon,
            model=body.model,
            direction="flat",
            error="Insufficient data. Need at least 10 bars; sync data for this symbol and range.",
        )

    try:
        feat = build_ohlcv_features(df, drop_na=True)
        if feat.empty:
            return ForecastResponse(
                success=False,
                symbol=body.symbol,
                from_date=body.from_date,
                to_date=body.to_date,
                horizon=body.horizon,
                model=body.model,
                direction="flat",
                error="Feature build produced no rows.",
            )
        macro_enriched = False
        if body.include_macro:
            try:
                macro_df = load_macro_features(body.from_date, body.to_date)
                if not macro_df.empty:
                    feat = join_macro_features(feat, macro_df)
                    macro_enriched = True
            except Exception:
                pass  # macro enrichment is best-effort; do not fail the forecast
        if body.model == "arima":
            model = ARIMAForecaster(order=(1, 0, 0)).fit(feat["close"])
        else:
            model = GBForecaster(n_lag=5).fit(feat["close"])
        pred = model.predict(horizon=body.horizon)
        direction = model.predict_direction(horizon=body.horizon)
        forecast_points = [
            ForecastPoint(step=i, value=float(pred.iloc[i]))
            for i in range(len(pred))
        ]
        try:
            register_forecast_run(
                symbol=body.symbol,
                from_date=body.from_date,
                to_date=body.to_date,
                horizon=body.horizon,
                model_type=body.model,
            )
        except Exception:
            pass  # registry is optional; do not fail the request
        return ForecastResponse(
            success=True,
            symbol=body.symbol,
            from_date=body.from_date,
            to_date=body.to_date,
            horizon=body.horizon,
            model=body.model,
            direction=direction,
            forecast=forecast_points,
            macro_enriched=macro_enriched,
            error=None,
        )
    except Exception as e:
        return ForecastResponse(
            success=False,
            symbol=body.symbol,
            from_date=body.from_date,
            to_date=body.to_date,
            horizon=body.horizon,
            model=body.model,
            direction="flat",
            error=str(e),
        )


@router.post("/evaluate", response_model=EvaluateForecastResponse)
async def evaluate_forecast_endpoint(
    body: EvaluateForecastRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """
    Evaluate forecast quality on a holdout period.

    Fits on [from_date, to_date - holdout_days], evaluates on the last holdout_days.
    Returns directional accuracy, RMSE, MAE, and simple backtest return from signals.
    """
    from_dt = parse_iso_date(body.from_date)
    to_dt = parse_iso_date(body.to_date)
    if from_dt is None or to_dt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD.",
        )

    try:
        df = load_underlying_series(body.symbol, from_date=from_dt, to_date=to_dt)
    except Exception as e:
        return EvaluateForecastResponse(
            success=False,
            symbol=body.symbol,
            directional_accuracy=0.0,
            rmse=0.0,
            mae=0.0,
            n_observations=0,
            error=f"Failed to load data: {e}",
        )

    if df.empty or len(df) < body.holdout_days + 20:
        return EvaluateForecastResponse(
            success=False,
            symbol=body.symbol,
            directional_accuracy=0.0,
            rmse=0.0,
            mae=0.0,
            n_observations=0,
            error=f"Need at least {body.holdout_days + 20} bars.",
        )

    try:
        feat = build_ohlcv_features(df, drop_na=True)
        if len(feat) < body.holdout_days + 10:
            return EvaluateForecastResponse(
                success=False,
                symbol=body.symbol,
                directional_accuracy=0.0,
                rmse=0.0,
                mae=0.0,
                n_observations=0,
                error="Insufficient rows after feature build.",
            )
        train = feat.iloc[: -body.holdout_days]
        holdout = feat.iloc[-body.holdout_days:]
        model = ARIMAForecaster(order=(1, 0, 0)).fit(train["close"])
        actual = holdout["close"]
        pred_series = model.predict(horizon=len(holdout))
        predicted = type(actual)(pred_series.values, index=actual.index)
        prev = float(train["close"].iloc[-1])
        signals_list = []
        for i in range(len(holdout)):
            p = float(predicted.iloc[i])
            s = "up" if p > prev else ("down" if p < prev else "flat")
            signals_list.append(s)
            prev = float(actual.iloc[i])
        signals = type(actual)(signals_list, index=actual.index)
        metrics = evaluate_forecast(actual, predicted)
        bt = backtest_returns_from_signals(actual, signals)
        return EvaluateForecastResponse(
            success=True,
            symbol=body.symbol,
            directional_accuracy=metrics["directional_accuracy"],
            rmse=metrics["rmse"],
            mae=metrics["mae"],
            n_observations=metrics["n_observations"],
            backtest_return=bt["total_return"],
            backtest_win_rate=bt["win_rate"],
            error=None,
        )
    except Exception as e:
        return EvaluateForecastResponse(
            success=False,
            symbol=body.symbol,
            directional_accuracy=0.0,
            rmse=0.0,
            mae=0.0,
            n_observations=0,
            error=str(e),
        )
