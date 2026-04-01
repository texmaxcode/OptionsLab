"""
Risk management API.

Provides position sizing calculations (Kelly Criterion, fixed fractional)
and break-even analysis for options strategies.

Routes
------
POST /risk/position-size   — Kelly + fixed-risk sizing
POST /risk/breakeven       — Break-even prices for a strategy
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api import auth_utils
from api.schemas import (
    BreakevenRequest,
    BreakevenResponse,
    PositionSizeRequest,
    PositionSizeResponse,
)
from models.sql_models import UserModel
from risk.position_sizing import (
    fixed_risk_size,
    half_kelly_fraction,
    kelly_fraction,
    max_contracts,
)
from strategy_engine.breakeven import compute_breakeven_prices
from strategy_engine.strategies import StrategyKind

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/position-size", response_model=PositionSizeResponse)
async def calculate_position_size(
    body: PositionSizeRequest,
    _: UserModel = Depends(auth_utils.get_current_user),
) -> PositionSizeResponse:
    """
    Calculate optimal position size using Kelly Criterion and fixed-risk methods.

    Inputs:
    - capital: Total account size in $
    - win_rate: Historical win rate (0.55 = 55 %)
    - avg_win: Average profit on winners in $
    - avg_loss: Average loss on losers in $ (unsigned)
    - max_risk_pct: Maximum risk per trade as % of capital (for fixed-risk)
    - max_loss_per_contract: Per-share max loss for options contracts

    Returns Kelly fraction, half-Kelly, fixed-risk units, and max contracts.
    """
    try:
        kf = kelly_fraction(body.win_rate, body.avg_win, body.avg_loss)
        hkf = half_kelly_fraction(body.win_rate, body.avg_win, body.avg_loss)

        k_dollar = round(body.capital * kf, 2) if kf is not None else None
        hk_dollar = round(body.capital * hkf, 2) if hkf is not None else None

        fr_dollar = round(body.capital * body.max_risk_pct / 100.0, 2)
        fr_units: float | None = None
        mc: int | None = None

        if body.max_loss_per_contract is not None:
            fr_units = fixed_risk_size(body.capital, body.max_risk_pct, body.max_loss_per_contract)
            if fr_units is not None:
                fr_units = round(fr_units, 2)
            mc = max_contracts(
                body.capital,
                body.max_risk_pct,
                body.max_loss_per_contract,
                body.contract_multiplier,
            )

        return PositionSizeResponse(
            success=True,
            kelly_fraction=round(kf, 4) if kf is not None else None,
            half_kelly_fraction=round(hkf, 4) if hkf is not None else None,
            kelly_dollar_risk=k_dollar,
            half_kelly_dollar_risk=hk_dollar,
            fixed_risk_dollar=fr_dollar,
            fixed_risk_units=fr_units,
            max_contracts=mc,
        )
    except Exception as exc:
        return PositionSizeResponse(success=False, error=str(exc))


@router.post("/breakeven", response_model=BreakevenResponse)
async def calculate_breakeven(
    body: BreakevenRequest,
    _: UserModel = Depends(auth_utils.get_current_user),
) -> BreakevenResponse:
    """
    Compute break-even underlying price(s) at expiry for an options strategy.

    For a strategy to be worth entering, the underlying must move beyond the
    break-even price(s) at expiry.  This calculation requires the premium paid
    (debit) or received (credit, expressed as negative).

    Supports: straddle, vertical_spread_call, vertical_spread_put,
              iron_condor, calendar_spread_call, calendar_spread_put.
    """
    try:
        kind = StrategyKind(body.strategy_type)
    except ValueError:
        return BreakevenResponse(
            success=False,
            strategy_type=body.strategy_type,
            error=f"Unknown strategy_type '{body.strategy_type}'. "
            f"Valid: {[k.value for k in StrategyKind]}",
        )

    params = {
        "strike": body.strike,
        "long_strike": body.long_strike,
        "short_strike": body.short_strike,
        "put_long": body.put_long,
        "put_short": body.put_short,
        "call_short": body.call_short,
        "call_long": body.call_long,
        "net_debit": body.net_debit,
    }

    try:
        prices = compute_breakeven_prices(kind, params, body.premium_paid)
        return BreakevenResponse(
            success=True,
            strategy_type=body.strategy_type,
            breakeven_prices=prices,
            premium_paid=body.premium_paid,
        )
    except Exception as exc:
        return BreakevenResponse(
            success=False,
            strategy_type=body.strategy_type,
            error=str(exc),
        )
