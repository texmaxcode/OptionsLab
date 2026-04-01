"""
Core backtest execution. Used by the API and by scripts/run_backtest.py.
Returns structured result (start_value, end_value, error) instead of printing.
"""

from typing import Any

from api.utils import parse_iso_date

import backtrader as bt

from backtrader_feeds import (
    OptionsPandasFeed,
    dataframe_from_storage_bars,
    underlying_bars_to_dataframe,
)
from models.sql_models import OptionsContractModel
from storage import (
    session_scope,
    OptionsContractRepository,
    OptionsBarRepository,
    UnderlyingBarRepository,
)
from strategies import (
    SingleLegOptionsStrategy,
    SmaCrossoverStrategy,
    SmaRsiStrategy,
    CoveredCallStrategy,
    ProtectivePutStrategy,
)
from strategies.equity_curve_analyzer import EquityCurveAnalyzer
from strategies.price_series_analyzer import PriceSeriesAnalyzer
from strategies.indicator_series_analyzer import IndicatorSeriesAnalyzer
from strategies.trade_list_analyzer import TradeListAnalyzer

STRATEGIES = {
    "single_leg": SingleLegOptionsStrategy,
    "sma_crossover": SmaCrossoverStrategy,
    "sma_rsi": SmaRsiStrategy,
    "covered_call": CoveredCallStrategy,
    "protective_put": ProtectivePutStrategy,
}

EQUITY_ONLY_STRATEGIES = ("sma_crossover", "sma_rsi")


def _compute_trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary stats from a list of trade dicts."""
    count = len(trades)
    if not count:
        return {
            "trade_count": 0,
            "win_rate": 0.0,
            "avg_pnl": None,
            "avg_win": None,
            "avg_loss": None,
            "best_trade_pnl": None,
            "worst_trade_pnl": None,
            "profit_factor": None,
            "avg_hold_days": None,
            "long_trades": 0,
            "short_trades": 0,
        }

    pnls = [float(t.get("pnl", 0.0)) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    win_rate = (len(wins) / count * 100.0) if count else 0.0
    avg_pnl = sum(pnls) / count
    avg_win = sum(wins) / len(wins) if wins else None
    avg_loss = sum(losses) / len(losses) if losses else None
    best_trade = max(pnls) if pnls else None
    worst_trade = min(pnls) if pnls else None

    gross_profit = sum(wins) if wins else 0.0
    gross_loss = sum(losses) if losses else 0.0
    profit_factor = (
        gross_profit / abs(gross_loss) if gross_loss < 0 and gross_profit > 0 else None
    )

    hold_days = [t.get("duration_days") for t in trades if t.get("duration_days") is not None]
    avg_hold_days = sum(hold_days) / len(hold_days) if hold_days else None

    long_trades = len([t for t in trades if t.get("direction") == "long"])
    short_trades = len([t for t in trades if t.get("direction") == "short"])

    return {
        "trade_count": count,
        "win_rate": round(win_rate, 2),
        "avg_pnl": round(avg_pnl, 2),
        "avg_win": round(avg_win, 2) if avg_win is not None else None,
        "avg_loss": round(avg_loss, 2) if avg_loss is not None else None,
        "best_trade_pnl": round(best_trade, 2) if best_trade is not None else None,
        "worst_trade_pnl": round(worst_trade, 2) if worst_trade is not None else None,
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "avg_hold_days": round(avg_hold_days, 2) if avg_hold_days is not None else None,
        "long_trades": long_trades,
        "short_trades": short_trades,
    }


def _compute_drawdown_curve(equity_curve: list[dict]) -> list[dict]:
    """From equity curve (list of {date, value}) compute drawdown % at each date."""
    out = []
    peak = 0.0
    for point in equity_curve:
        v = point["value"]
        if v > peak:
            peak = v
        dd_pct = ((peak - v) / peak * 100.0) if peak > 0 else 0.0
        out.append({"date": point["date"], "drawdown": round(dd_pct, 2)})
    return out


def _extract_chart_data(strat) -> dict[str, Any]:
    """Extract equity curve, drawdown, returns, price series, indicators, and trades from analyzers."""
    equity_curve = []
    time_returns = []
    price_series = []
    indicator_series = []
    trades = []

    eq_ana = strat.analyzers.getbyname("equity_curve")
    if eq_ana:
        equity_curve = eq_ana.get_analysis().get("equity_curve") or []

    tr_ana = strat.analyzers.getbyname("timereturn")
    if tr_ana:
        raw = tr_ana.get_analysis()
        for dt, ret in raw.items():
            date_iso = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
            time_returns.append({"date": date_iso, "period_return": round(float(ret), 6)})

    ps_ana = strat.analyzers.getbyname("price_series")
    if ps_ana:
        price_series = ps_ana.get_analysis().get("price_series") or []

    ind_ana = strat.analyzers.getbyname("indicator_series")
    if ind_ana:
        indicator_series = ind_ana.get_analysis().get("indicator_series") or []

    trade_ana = strat.analyzers.getbyname("trade_list")
    if trade_ana:
        trades = trade_ana.get_analysis().get("trades") or []

    drawdown_curve = _compute_drawdown_curve(equity_curve) if equity_curve else []

    return {
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "time_returns": time_returns,
        "price_series": price_series,
        "indicator_series": indicator_series,
        "trades": trades,
    }


def run_backtest(
    strategy: str,
    underlying: str,
    from_date: str | None = None,
    to_date: str | None = None,
    cash: float = 100_000.0,
    contract_id: int | None = None,
    contract_symbol: str | None = None,
    first_contract: bool = False,
    no_plot: bool = True,
) -> dict[str, Any]:
    """
    Run a backtest and return a result dict with success, start_value, end_value, error.
    All date strings are YYYY-MM-DD. For equity-only strategies, from_date and to_date are required.
    """
    from_dt = parse_iso_date(from_date)
    to_dt = parse_iso_date(to_date)

    if strategy not in STRATEGIES:
        return {
            "success": False,
            "start_value": None,
            "end_value": None,
            "equity_curve": None,
            "error": f"Unknown strategy: {strategy}",
        }

    strategy_cls = STRATEGIES[strategy]

    with session_scope() as session:
        underlying_repo = UnderlyingBarRepository(session)

        if strategy in EQUITY_ONLY_STRATEGIES:
            if from_dt is None or to_dt is None:
                return {
                    "success": False,
                    "start_value": None,
                    "end_value": None,
                    "equity_curve": None,
                    "error": "Equity strategies require from_date and to_date.",
                }
            underlying_bars = underlying_repo.get_bars(
                underlying, from_date=from_dt, to_date=to_dt
            )
            if not underlying_bars:
                return {
                    "success": False,
                    "start_value": None,
                    "end_value": None,
                    "equity_curve": None,
                    "error": f"No underlying bars in DB for {underlying}.",
                }
            df = underlying_bars_to_dataframe(underlying_bars)
            cerebro = bt.Cerebro()
            cerebro.broker.setcash(cash)
            cerebro.adddata(bt.feeds.PandasData(dataname=df), name="underlying")
            cerebro.addanalyzer(EquityCurveAnalyzer, _name="equity_curve")
            cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn")
            cerebro.addanalyzer(PriceSeriesAnalyzer, _name="price_series")
            cerebro.addanalyzer(IndicatorSeriesAnalyzer, _name="indicator_series")
            cerebro.addanalyzer(TradeListAnalyzer, _name="trade_list")
            cerebro.addstrategy(strategy_cls)
            start_value = cerebro.broker.getvalue()
            run_result = cerebro.run()
            end_value = cerebro.broker.getvalue()
            chart_data = {}
            if run_result:
                chart_data = _extract_chart_data(run_result[0])
            trades = chart_data.get("trades") or []
            chart_data["trade_stats"] = _compute_trade_stats(trades)
            return {
                "success": True,
                "start_value": start_value,
                "end_value": end_value,
                "equity_curve": chart_data.get("equity_curve") or [],
                "chart_data": chart_data,
                "error": None,
            }

        # Options strategies
        contract_repo = OptionsContractRepository(session)
        bar_repo = OptionsBarRepository(session)

        contract = None
        if contract_id is not None:
            contract = session.get(OptionsContractModel, contract_id)
        elif contract_symbol:
            contract = contract_repo.get_by_contract_symbol(contract_symbol)
        elif first_contract:
            contracts = contract_repo.list_contracts(underlying_symbol=underlying)
            if not contracts:
                return {
                    "success": False,
                    "start_value": None,
                    "end_value": None,
                    "equity_curve": None,
                    "error": f"No options contracts found for underlying {underlying}.",
                }
            contract = contracts[0]

        if not contract:
            return {
                "success": False,
                "start_value": None,
                "end_value": None,
                "equity_curve": None,
                "error": "No contract specified or found. Use contract_id, contract_symbol, or first_contract.",
            }

        bars = bar_repo.get_bars_for_contract_with_contract(
            contract.id, from_date=from_dt, to_date=to_dt
        )
        if not bars:
            return {
                "success": False,
                "start_value": None,
                "end_value": None,
                "equity_curve": None,
                "error": "No options bars in DB for this contract/date range.",
            }

        df_option = dataframe_from_storage_bars(bars)
        if df_option.empty:
            return {
                "success": False,
                "start_value": None,
                "end_value": None,
                "equity_curve": None,
                "error": "Options DataFrame empty.",
            }

        cerebro = bt.Cerebro()
        cerebro.broker.setcash(cash)
        option_feed = OptionsPandasFeed(
            dataname=df_option,
            strike=contract.strike,
            expiration=contract.expiration,
            option_type=contract.option_type,
        )
        cerebro.adddata(option_feed, name="option")

        underlying_bars = underlying_repo.get_bars(
            contract.underlying_symbol,
            from_date=from_dt,
            to_date=to_dt,
        )
        if underlying_bars:
            df_underlying = underlying_bars_to_dataframe(underlying_bars)
            cerebro.adddata(
                bt.feeds.PandasData(dataname=df_underlying), name="underlying"
            )
        elif strategy in ("covered_call", "protective_put"):
            return {
                "success": False,
                "start_value": None,
                "end_value": None,
                "equity_curve": None,
                "error": "Covered call and protective put require underlying data in DB.",
            }

        cerebro.addanalyzer(EquityCurveAnalyzer, _name="equity_curve")
        cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn")
        cerebro.addanalyzer(PriceSeriesAnalyzer, _name="price_series")
        cerebro.addanalyzer(IndicatorSeriesAnalyzer, _name="indicator_series")
        cerebro.addanalyzer(TradeListAnalyzer, _name="trade_list")
        cerebro.addstrategy(strategy_cls)
        start_value = cerebro.broker.getvalue()
        run_result = cerebro.run()
        end_value = cerebro.broker.getvalue()
        chart_data = {}
        if run_result:
            chart_data = _extract_chart_data(run_result[0])
        trades = chart_data.get("trades") or []
        chart_data["trade_stats"] = _compute_trade_stats(trades)
        return {
            "success": True,
            "start_value": start_value,
            "end_value": end_value,
            "equity_curve": chart_data.get("equity_curve") or [],
            "chart_data": chart_data,
            "error": None,
        }
