"""Lab backtests: history and creation tied to users."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import auth_utils
from api.utils import parse_iso_date
from api.schemas import (
    BacktestCreateRequest,
    BacktestUpdateRequest,
    BacktestDetail,
    BacktestSummary,
    DashboardSummary,
    DrawdownPoint,
    EquityCurvePoint,
    IndicatorPoint,
    PricePoint,
    SegmentStats,
    TimeReturnPoint,
    Trade,
    TradeStats,
)
from api.services.run_backtest import (
    EQUITY_ONLY_STRATEGIES,
    run_backtest,
    _compute_trade_stats,
    _compute_drawdown_curve,
)
from models.sql_models import (
    BacktestModel,
    BacktestEquityPointModel,
    BacktestIndicatorPointModel,
    BacktestPricePointModel,
    BacktestReturnPointModel,
    BacktestTradeModel,
    UserModel,
    utcnow_naive,
)
from storage import session_scope


router = APIRouter(prefix="/lab", tags=["lab"])


def _backtest_to_detail(bt: BacktestModel, session: Session) -> BacktestDetail:
    """Build BacktestDetail from normalized result tables."""
    # New normalized tables take precedence
    equity_curve: list[EquityCurvePoint] | None = None
    drawdown_curve: list[DrawdownPoint] | None = None
    time_returns: list[TimeReturnPoint] | None = None
    price_series: list[PricePoint] | None = None
    indicator_series: list[IndicatorPoint] | None = None
    trades: list[Trade] | None = None
    trade_stats: TradeStats | None = None

    eq_rows = (
        session.execute(
            select(BacktestEquityPointModel)
            .where(BacktestEquityPointModel.backtest_id == bt.id)
            .order_by(BacktestEquityPointModel.date)
        )
        .scalars()
        .all()
    )
    if eq_rows:
        equity_curve = [
            EquityCurvePoint(date=row.date.date().isoformat(), value=row.value) for row in eq_rows
        ]
        # _compute_drawdown_curve expects list[dict] with date/value; convert dates to iso later
        dd = _compute_drawdown_curve(
            [{"date": row.date.date().isoformat(), "value": row.value} for row in eq_rows]
        )
        drawdown_curve = [
            DrawdownPoint(date=p["date"], drawdown=p["drawdown"]) for p in dd  # type: ignore[index]
        ]

    ret_rows = (
        session.execute(
            select(BacktestReturnPointModel)
            .where(BacktestReturnPointModel.backtest_id == bt.id)
            .order_by(BacktestReturnPointModel.date)
        )
        .scalars()
        .all()
    )
    if ret_rows:
        by_date: dict[str, TimeReturnPoint] = {}
        for row in ret_rows:
            date_str = row.date.date().isoformat()
            by_date[date_str] = TimeReturnPoint(
                date=date_str,
                period_return=row.period_return,
            )
        time_returns = [by_date[d] for d in sorted(by_date)]

    price_rows = (
        session.execute(
            select(BacktestPricePointModel)
            .where(BacktestPricePointModel.backtest_id == bt.id)
            .order_by(BacktestPricePointModel.date)
        )
        .scalars()
        .all()
    )
    if price_rows:
        price_series = [
            PricePoint(date=row.date.date().isoformat(), close=row.close) for row in price_rows
        ]

    trade_rows = (
        session.execute(
            select(BacktestTradeModel)
            .where(BacktestTradeModel.backtest_id == bt.id)
            .order_by(BacktestTradeModel.entry_date)
        )
        .scalars()
        .all()
    )
    if trade_rows:
        trades = [
            Trade(
                entry_date=row.entry_date.date().isoformat(),
                exit_date=row.exit_date.date().isoformat() if row.exit_date else None,
                direction=row.direction,
                size=row.size,
                entry_price=row.entry_price,
                exit_price=row.exit_price,
                pnl=row.pnl,
                pnl_pct=row.pnl_pct,
                duration_days=int(row.duration_days) if row.duration_days is not None else None,
            )
            for row in trade_rows
        ]
        trade_stats = TradeStats(**_compute_trade_stats([t.model_dump() for t in trades]))

    ind_rows = (
        session.execute(
            select(BacktestIndicatorPointModel)
            .where(BacktestIndicatorPointModel.backtest_id == bt.id)
            .order_by(BacktestIndicatorPointModel.date)
        )
        .scalars()
        .all()
    )
    if ind_rows:
        indicator_series = [
            IndicatorPoint(
                date=row.date.date().isoformat(),
                indicators=json.loads(row.indicators_json or "{}"),
            )
            for row in ind_rows
        ]

    return BacktestDetail(
        id=bt.id,
        name=bt.name,
        created_at=bt.created_at,
        strategy=bt.strategy,
        underlying=bt.underlying,
        from_date=bt.from_date.strftime("%Y-%m-%d") if bt.from_date else None,
        to_date=bt.to_date.strftime("%Y-%m-%d") if bt.to_date else None,
        cash=bt.cash,
        status=bt.status,
        start_value=bt.start_value,
        end_value=bt.end_value,
        contract_id=bt.contract_id,
        contract_symbol=bt.contract_symbol,
        first_contract=bt.first_contract,
        error=bt.error,
        equity_curve=equity_curve,
        drawdown_curve=drawdown_curve,
        time_returns=time_returns,
        price_series=price_series,
        indicator_series=indicator_series,
        trades=trades,
        trade_stats=trade_stats,
    )


def _collect_trades(backtests: list[BacktestModel], session: Session) -> list[dict]:
    """Collect all trades from normalized backtest_trades table for given backtests."""
    trades: list[dict] = []
    for bt in backtests:
        rows = (
            session.execute(
                select(BacktestTradeModel)
                .where(BacktestTradeModel.backtest_id == bt.id)
                .order_by(BacktestTradeModel.entry_date)
            )
            .scalars()
            .all()
        )
        for row in rows:
            trades.append({
                "entry_date": row.entry_date.date().isoformat(),
                "exit_date": row.exit_date.date().isoformat() if row.exit_date else None,
                "direction": row.direction,
                "size": row.size,
                "entry_price": row.entry_price,
                "exit_price": row.exit_price,
                "pnl": row.pnl,
                "pnl_pct": row.pnl_pct,
                "duration_days": row.duration_days,
            })
    return trades


def _compute_segment_stats(backtests: list[BacktestModel]) -> SegmentStats:
    total = len(backtests)
    completed_with_values: list[BacktestModel] = [
        b
        for b in backtests
        if b.status == "completed" and b.start_value not in (None, 0) and b.end_value is not None
    ]
    completed = len(completed_with_values)
    if not completed:
        return SegmentStats(
            total=total,
            completed=completed,
            win_rate=0.0,
            avg_return_pct=None,
            best_return_pct=None,
            worst_return_pct=None,
        )

    returns: list[float] = []
    wins = 0
    for b in completed_with_values:
        ret = (b.end_value - b.start_value) / b.start_value * 100.0
        returns.append(ret)
        if ret > 0:
            wins += 1

    win_rate = wins / completed * 100.0
    avg_ret = sum(returns) / len(returns)
    best_ret = max(returns)
    worst_ret = min(returns)

    return SegmentStats(
        total=total,
        completed=completed,
        win_rate=round(win_rate, 2),
        avg_return_pct=round(avg_ret, 2),
        best_return_pct=round(best_ret, 2),
        worst_return_pct=round(worst_ret, 2),
    )


def _compute_overall_curve(backtests: list[BacktestModel]) -> list[EquityCurvePoint]:
    equity = 1.0
    points: list[EquityCurvePoint] = []
    # sort by created_at so curve progresses over time
    for b in sorted(backtests, key=lambda x: x.created_at):
        if b.status != "completed" or b.start_value in (None, 0) or b.end_value is None:
            continue
        ret = (b.end_value - b.start_value) / b.start_value
        equity *= 1.0 + ret
        points.append(
            EquityCurvePoint(
                date=b.created_at.date().isoformat(),
                value=round(equity, 4),
            )
        )
    return points


@router.get("/backtests", response_model=list[BacktestSummary])
async def list_backtests(current_user: UserModel = Depends(auth_utils.get_current_user)):
    """List backtests for the current user, newest first."""
    with session_scope() as session:
        stmt = (
            select(BacktestModel)
            .where(BacktestModel.user_id == current_user.id)
            .order_by(BacktestModel.created_at.desc())
        )
        backtests = session.execute(stmt).scalars().all()
        return [
            BacktestSummary(
                id=b.id,
                name=b.name,
                created_at=b.created_at,
                strategy=b.strategy,
                underlying=b.underlying,
                from_date=b.from_date.strftime("%Y-%m-%d") if b.from_date else None,
                to_date=b.to_date.strftime("%Y-%m-%d") if b.to_date else None,
                cash=b.cash,
                status=b.status,
                start_value=b.start_value,
                end_value=b.end_value,
            )
            for b in backtests
        ]


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Return aggregate stats for overall, equity-only, and options backtests."""
    with session_scope() as session:
        stmt = select(BacktestModel).where(BacktestModel.user_id == current_user.id)
        backtests = list(session.execute(stmt).scalars().all())
        overall_stats = _compute_segment_stats(backtests)
        equity_backtests = [b for b in backtests if b.strategy in EQUITY_ONLY_STRATEGIES]
        options_backtests = [b for b in backtests if b.strategy not in EQUITY_ONLY_STRATEGIES]

        equity_stats = _compute_segment_stats(equity_backtests)
        options_stats = _compute_segment_stats(options_backtests)

        overall_trade_stats = _compute_trade_stats(_collect_trades(backtests, session))
        equity_trade_stats = _compute_trade_stats(_collect_trades(equity_backtests, session))
        options_trade_stats = _compute_trade_stats(_collect_trades(options_backtests, session))

        return DashboardSummary(
            overall=overall_stats,
            equity=equity_stats,
            options=options_stats,
            overall_equity_curve=_compute_overall_curve(backtests),
            equity_equity_curve=_compute_overall_curve(equity_backtests),
            options_equity_curve=_compute_overall_curve(options_backtests),
            overall_trade_stats=TradeStats(**overall_trade_stats),
            equity_trade_stats=TradeStats(**equity_trade_stats),
            options_trade_stats=TradeStats(**options_trade_stats),
        )


@router.post("/backtests", response_model=BacktestDetail)
async def create_backtest(
    body: BacktestCreateRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Create and run a new backtest, then persist it."""
    result = run_backtest(
        strategy=body.strategy,
        underlying=body.underlying,
        from_date=body.from_date,
        to_date=body.to_date,
        cash=body.cash,
        contract_id=body.contract_id,
        contract_symbol=body.contract_symbol,
        first_contract=body.first_contract,
        no_plot=True,
    )

    status_value = "completed" if result["success"] else "failed"
    chart_data = result.get("chart_data") or {}
    equity_curve = result.get("equity_curve") or chart_data.get("equity_curve") or []

    with session_scope() as session:
        bt = BacktestModel(
            user_id=current_user.id,
            name=body.name,
            created_at=utcnow_naive(),
            strategy=body.strategy,
            underlying=body.underlying,
            from_date=parse_iso_date(body.from_date),
            to_date=parse_iso_date(body.to_date),
            cash=body.cash,
            contract_id=body.contract_id,
            contract_symbol=body.contract_symbol,
            first_contract=body.first_contract,
            status=status_value,
            start_value=result.get("start_value"),
            end_value=result.get("end_value"),
            error=result.get("error"),
        )
        session.add(bt)
        session.flush()  # ensure bt.id is available for result tables

        # Persist normalized result data for fast retrieval
        if status_value == "completed" and chart_data:
            # Equity curve
            eq_points = chart_data.get("equity_curve") or equity_curve or []
            for p in eq_points:
                dt = parse_iso_date(p.get("date"))
                if dt is None:
                    continue
                session.add(
                    BacktestEquityPointModel(
                        backtest_id=bt.id,
                        date=dt,
                        value=float(p.get("value", 0.0)),
                    )
                )

            # Period returns
            for p in chart_data.get("time_returns") or []:
                dt = parse_iso_date(p.get("date"))
                if dt is None:
                    continue
                session.add(
                    BacktestReturnPointModel(
                        backtest_id=bt.id,
                        date=dt,
                        period_return=float(p.get("period_return", 0.0)),
                    )
                )

            # Price series (for price/indicators/trades chart)
            for p in chart_data.get("price_series") or []:
                dt = parse_iso_date(p.get("date"))
                if dt is None:
                    continue
                session.add(
                    BacktestPricePointModel(
                        backtest_id=bt.id,
                        date=dt,
                        close=float(p.get("close", 0.0)),
                    )
                )

            # Trades
            for t in chart_data.get("trades") or []:
                entry_dt = parse_iso_date(t.get("entry_date"))
                if entry_dt is None:
                    continue
                exit_dt = parse_iso_date(t.get("exit_date"))
                session.add(
                    BacktestTradeModel(
                        backtest_id=bt.id,
                        entry_date=entry_dt,
                        exit_date=exit_dt,
                        direction=str(t.get("direction", "")),
                        size=float(t.get("size", 0.0)),
                        entry_price=float(t.get("entry_price", 0.0)),
                        exit_price=(
                            float(t["exit_price"]) if t.get("exit_price") is not None else None
                        ),
                        pnl=float(t.get("pnl", 0.0)),
                        pnl_pct=(
                            float(t["pnl_pct"]) if t.get("pnl_pct") is not None else None
                        ),
                        duration_days=(
                            float(t["duration_days"])
                            if t.get("duration_days") is not None
                            else None
                        ),
                    )
                )

            # Indicator series
            for p in chart_data.get("indicator_series") or []:
                dt = parse_iso_date(p.get("date"))
                if dt is None:
                    continue
                indicators = p.get("indicators") or {}
                session.add(
                    BacktestIndicatorPointModel(
                        backtest_id=bt.id,
                        date=dt,
                        indicators_json=json.dumps(indicators),
                    )
                )

        session.commit()
        session.refresh(bt)
        return _backtest_to_detail(bt, session)


@router.get("/backtests/{backtest_id}", response_model=BacktestDetail)
async def get_backtest(
    backtest_id: int,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Get a single backtest for the current user."""
    with session_scope() as session:
        bt = session.get(BacktestModel, backtest_id)
        if bt is None or bt.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return _backtest_to_detail(bt, session)


@router.patch("/backtests/{backtest_id}")
def update_backtest(
    backtest_id: int,
    body: BacktestUpdateRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Update backtest fields (e.g. name)."""
    with session_scope() as session:
        bt = session.get(BacktestModel, backtest_id)
        if bt is None or bt.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        if body.name is not None and body.name.strip():
            bt.name = body.name.strip()[:128]
        session.commit()
        session.refresh(bt)
        return _backtest_to_detail(bt, session)


@router.delete("/backtests/{backtest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backtest(
    backtest_id: int,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Delete a backtest and all its stored data for the current user.

    Removes the backtest row entirely, including equity curve, result JSON
    (price series, indicators, trades, drawdown, period returns), and all metadata.
    """
    with session_scope() as session:
        bt = session.get(BacktestModel, backtest_id)
        if bt is None or bt.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        session.delete(bt)
        session.commit()

