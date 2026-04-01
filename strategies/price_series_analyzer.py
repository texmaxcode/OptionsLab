"""Backtrader Analyzer that records close price of the main data feed at each bar."""

import backtrader as bt


class PriceSeriesAnalyzer(bt.Analyzer):
    """Records (date_iso, close) at each bar. Use get_analysis()['price_series']."""

    def __init__(self):
        self.price_series = []

    def next(self):
        try:
            dt = self.strategy.datetime.date(0)
            date_iso = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
            close = float(self.strategy.datas[0].close[0])
            self.price_series.append({"date": date_iso, "close": round(close, 4)})
        except Exception:
            pass

    def get_analysis(self):
        return {"price_series": self.price_series}
