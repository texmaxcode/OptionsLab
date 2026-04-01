"""
SMA Crossover strategy (stock/underlying only).

Classic trend-following: buy when fast SMA crosses above slow SMA, sell when fast
crosses below slow. Uses a single data feed (underlying equity).
"""

import backtrader as bt


class SmaCrossoverStrategy(bt.Strategy):
    """
    Two moving-average crossover on data0 (underlying).
    Buy when fast SMA crosses above slow SMA; sell when fast crosses below slow.
    """

    params = (
        ("fast_period", 20),
        ("slow_period", 50),
        ("size", 100),
    )

    def __init__(self) -> None:
        self.data = self.datas[0]
        self.fast = bt.indicators.SimpleMovingAverage(self.data.close, period=self.params.fast_period)
        self.slow = bt.indicators.SimpleMovingAverage(self.data.close, period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.fast, self.slow)
        self.order = None

    def notify_order(self, order: bt.Order) -> None:
        if order.status in (order.Completed, order.Canceled, order.Margin):
            self.order = None

    def next(self) -> None:
        self._indicator_values = {
            "close": float(self.data.close[0]),
            "sma_fast": float(self.fast[0]),
            "sma_slow": float(self.slow[0]),
        }
        if self.order:
            return
        pos = self.getposition(self.data).size
        if not pos and self.crossover > 0:
            self.order = self.buy(data=self.data, size=self.params.size)
        elif pos and self.crossover < 0:
            self.order = self.close(data=self.data)
