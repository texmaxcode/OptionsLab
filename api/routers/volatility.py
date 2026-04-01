"""
Volatility analytics API.

Provides Historical Volatility (HV) at multiple lookback windows,
Implied Volatility (IV) series from stored options bars, IV Rank, IV Percentile,
and Expected Move — the key inputs for deciding *when* to enter an options strategy.

Route
-----
GET /volatility/{symbol}?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Query

from api import auth_utils
from api.schemas import HVDataPoint, IVDataPoint, VolatilityResponse
from api.utils import parse_iso_date
from features import load_underlying_series
from models.sql_models import UserModel
from storage import session_scope
from storage.repositories import OptionsBarRepository
from volatility.metrics import (
    expected_move,
    historical_volatility,
    hv_series,
    iv_percentile,
    iv_rank,
)

router = APIRouter(prefix="/volatility", tags=["volatility"])


@router.get("/{symbol}", response_model=VolatilityResponse)
async def get_volatility(
    symbol: str,
    from_date: str = Query(..., description="Start date YYYY-MM-DD"),
    to_date: str = Query(..., description="End date YYYY-MM-DD"),
    _: UserModel = Depends(auth_utils.get_current_user),
) -> VolatilityResponse:
    """
    Return volatility metrics for *symbol* over the requested date range.

    Requires underlying OHLCV bars to be synced (for HV).
    Optionally uses stored options bars for IV (if any contracts have been synced).

    Response includes:
    - Historical Volatility at 10/20/30/60-day windows
    - IV Rank and IV Percentile (0–100) based on all stored IV data
    - Expected Move over 30 calendar days (1σ)
    - Time series for IV and 20-day HV charting
    """
    from_dt = parse_iso_date(from_date)
    to_dt = parse_iso_date(to_date)
    if from_dt is None or to_dt is None:
        return VolatilityResponse(
            success=False,
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            error="Invalid date format. Use YYYY-MM-DD.",
        )

    # --- Load underlying OHLCV for HV computation ---
    try:
        df = load_underlying_series(symbol, from_date=from_dt, to_date=to_dt)
    except Exception as exc:
        return VolatilityResponse(
            success=False,
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            error=f"Failed to load underlying bars: {exc}",
        )

    if df.empty or len(df) < 5:
        return VolatilityResponse(
            success=False,
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            error="Insufficient underlying bar data. Sync OHLCV data for this symbol first.",
        )

    closes = df["close"].dropna()
    current_price = float(closes.iloc[-1]) if not closes.empty else None

    hv10 = historical_volatility(closes, 10)
    hv20 = historical_volatility(closes, 20)
    hv30 = historical_volatility(closes, 30)
    hv60 = historical_volatility(closes, 60)

    # Build 20-day HV time series for charting
    hv20_rolling = hv_series(closes, 20)
    hv20_series_data: list[HVDataPoint] = []
    for idx, val in hv20_rolling.dropna().items():
        date_str = str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]
        hv20_series_data.append(HVDataPoint(date=date_str, hv=round(float(val), 6)))

    # --- Load IV series from stored options bars ---
    iv_series_data: list[IVDataPoint] = []
    current_iv: float | None = None
    ivr: float | None = None
    ivp: float | None = None
    em_dollar: float | None = None
    em_pct: float | None = None

    try:
        with session_scope() as session:
            bar_repo = OptionsBarRepository(session)
            iv_rows = bar_repo.get_daily_iv_series(symbol, from_date=from_dt, to_date=to_dt)

        if iv_rows:
            iv_df = pd.DataFrame(iv_rows).set_index("date")["iv"]
            iv_series_data = [
                IVDataPoint(date=str(date), iv=round(float(val), 6))
                for date, val in iv_df.items()
                if not pd.isna(val)
            ]
            if not iv_df.empty:
                current_iv = float(iv_df.iloc[-1])
                ivr = iv_rank(current_iv, iv_df)
                ivp = iv_percentile(current_iv, iv_df)
                if current_price and current_iv:
                    em_dollar_val = expected_move(current_price, current_iv, 30)
                    em_dollar = round(em_dollar_val, 2)
                    em_pct = round(em_dollar_val / current_price * 100, 2)
    except Exception:
        # IV data is optional — proceed without it
        pass

    return VolatilityResponse(
        success=True,
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        current_price=round(current_price, 2) if current_price else None,
        current_iv=round(current_iv, 4) if current_iv else None,
        hv_10=round(hv10, 4) if hv10 else None,
        hv_20=round(hv20, 4) if hv20 else None,
        hv_30=round(hv30, 4) if hv30 else None,
        hv_60=round(hv60, 4) if hv60 else None,
        iv_rank=ivr,
        iv_percentile=ivp,
        expected_move_30d_dollar=em_dollar,
        expected_move_30d_pct=em_pct,
        iv_series=iv_series_data,
        hv_20_series=hv20_series_data,
    )
