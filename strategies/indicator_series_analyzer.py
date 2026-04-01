"""Backtrader Analyzer that records strategy._indicator_values at each bar if set."""

import backtrader as bt


class IndicatorSeriesAnalyzer(bt.Analyzer):
    """
    Records (date_iso, indicators_dict) at each bar when strategy sets _indicator_values.
    Strategies can set self._indicator_values = {'sma_fast': 100.5, 'sma_slow': 99.2, ...} in next().
    Use get_analysis()['indicator_series'].
    """

    def __init__(self):
        self.indicator_series = []

    def next(self):
        try:
            vals = getattr(self.strategy, "_indicator_values", None)
            if not vals or not isinstance(vals, dict):
                return
            dt = self.strategy.datetime.date(0)
            date_iso = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
            rounded = {k: round(float(v), 6) for k, v in vals.items()}
            self.indicator_series.append({"date": date_iso, "indicators": rounded})
        except Exception:
            pass

    def get_analysis(self):
        return {"indicator_series": self.indicator_series}
