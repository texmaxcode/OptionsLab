"""
Backtrader Analyzer that records portfolio value at each bar for charting.
"""

import backtrader as bt


class EquityCurveAnalyzer(bt.Analyzer):
    """Records (date_iso, portfolio_value) at each bar. Use get_analysis()['equity_curve']."""

    def __init__(self):
        self.equity_curve = []

    def next(self):
        try:
            dt = self.strategy.datetime.date(0)
            date_iso = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
            value = self.strategy.broker.getvalue()
            self.equity_curve.append({"date": date_iso, "value": round(value, 2)})
        except Exception:
            pass

    def get_analysis(self):
        return {"equity_curve": self.equity_curve}
