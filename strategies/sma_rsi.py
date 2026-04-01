"""
SMA Crossover + RSI filter strategy (stock/underlying only).

Trend-following with momentum filter: buy on fast-above-slow crossover only when
RSI is not overbought; sell on fast-below-slow only when RSI is not oversold.
Reduces false signals in choppy markets.
"""

import backtrader as bt


class SmaRsiStrategy(bt.Strategy):
    """
    SMA crossover with RSI filter on data0 (underlying).
    Buy when fast > slow and RSI < overbought; sell when fast < slow and RSI > oversold.
    """

    params = (
        ("fast_period", 20),
        ("slow_period", 50),
        ("rsi_period", 14),
        ("rsi_overbought", 70),
        ("rsi_oversold", 30),
        ("size", 100),
    )

    def __init__(self) -> None:
        self.data = self.datas[0]
        self.fast = bt.indicators.SimpleMovingAverage(self.data.close, period=self.params.fast_period)
        self.slow = bt.indicators.SimpleMovingAverage(self.data.close, period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.fast, self.slow)
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.order = None

    def notify_order(self, order: bt.Order) -> None:
        if order.status in (order.Completed, order.Canceled, order.Margin):
            self.order = None

    def next(self) -> None:
        self._indicator_values = {
            "close": float(self.data.close[0]),
            "sma_fast": float(self.fast[0]),
            "sma_slow": float(self.slow[0]),
            "rsi": float(self.rsi[0]),
        }
        if self.order:
            return
        pos = self.getposition(self.data).size
        rsi_ok_buy = self.rsi[0] < self.params.rsi_overbought
        rsi_ok_sell = self.rsi[0] > self.params.rsi_oversold
        if not pos and self.crossover > 0 and rsi_ok_buy:
            self.order = self.buy(data=self.data, size=self.params.size)
        elif pos and self.crossover < 0 and rsi_ok_sell:
            self.order = self.close(data=self.data)
