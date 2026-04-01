"""Tests for strategies.trade_list_analyzer.TradeListAnalyzer."""

from datetime import datetime

import backtrader as bt
import pandas as pd

from strategies.trade_list_analyzer import TradeListAnalyzer


class _BuySellOnceStrategy(bt.Strategy):
    """Minimal strategy: buy at bar 1, sell at bar 2 to produce one closed trade."""

    def next(self):
        if len(self) == 1:
            self.buy(size=100)
        elif len(self) == 2:
            self.close()


def test_trade_list_analyzer_via_cerebro() -> None:
    """Run Cerebro with TradeListAnalyzer; one closed trade is recorded."""
    df = pd.DataFrame({
        "datetime": pd.to_datetime([datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 1, 3)]),
        "open": [100.0, 101.0, 102.0],
        "high": [101.0, 102.0, 103.0],
        "low": [99.0, 100.0, 101.0],
        "close": [100.5, 101.5, 102.5],
        "volume": [1000, 1000, 1000],
    }).set_index("datetime")

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000.0)
    cerebro.adddata(bt.feeds.PandasData(dataname=df))
    cerebro.addstrategy(_BuySellOnceStrategy)
    cerebro.addanalyzer(TradeListAnalyzer, _name="trade_list")
    results = cerebro.run()

    strat = results[0]
    analyzer = strat.analyzers.getbyname("trade_list")
    analysis = analyzer.get_analysis()
    assert "trades" in analysis
    assert len(analysis["trades"]) == 1
    t = analysis["trades"][0]
    assert t["direction"] in ("long", "flat")  # Backtrader may report 0 size when closed
    assert "entry_date" in t and "exit_date" in t
    assert "entry_price" in t and "exit_price" in t
    assert "pnl" in t and "pnl_pct" in t
    assert "duration_days" in t
