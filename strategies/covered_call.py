"""
Covered Call strategy: long underlying + short call.

Uses data0 = option (call to sell), data1 = underlying (stock to hold).
Opens long underlying and short call; closes short call before expiry.
Assumes 1 option contract per 100 shares (multiplier); size in options is in contracts.
"""

import backtrader as bt

from strategies.option_expiry_utils import is_expired_or_near


class CoveredCallStrategy(bt.Strategy):
    """
    Long underlying (data1) and short call (data0). Exit short option before expiry.
    params.underlying_size: shares to buy (e.g. 100 per contract).
    params.option_size: number of call contracts to sell (positive = short).
    """

    params = (
        ("exit_before_expiry", True),
        ("expiry_days_before", 1),
        ("underlying_size", 100),
        ("option_size", 1),
    )

    def __init__(self) -> None:
        self.option_data = self.datas[0]
        self.underlying_data = self.datas[1] if len(self.datas) > 1 else None
        self.expiration = getattr(self.option_data.params, "expiration", None)
        self.order = None
        self.short_call_done = False

    def notify_order(self, order: bt.Order) -> None:
        if order.status in (order.Completed, order.Canceled, order.Margin):
            self.order = None

    def _is_expired_or_near(self) -> bool:
        cur = self.option_data.datetime.datetime(0)
        return is_expired_or_near(
            cur,
            self.expiration,
            self.params.exit_before_expiry,
            self.params.expiry_days_before,
        )

    def next(self) -> None:
        if self.order:
            return
        opt_pos = self.getposition(self.option_data).size
        und_pos = self.getposition(self.underlying_data).size if self.underlying_data else 0

        if opt_pos < 0 and self._is_expired_or_near():
            self.close(data=self.option_data)
            return
        if self.underlying_data and und_pos <= 0 and len(self) >= 1:
            self.order = self.buy(data=self.underlying_data, size=self.params.underlying_size)
            return
        if und_pos > 0 and not self.short_call_done and opt_pos == 0:
            self.short_call_done = True
            self.order = self.sell(data=self.option_data, size=self.params.option_size)
