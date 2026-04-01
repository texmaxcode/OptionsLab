"""Single-leg options strategy: long call or put with expiry awareness."""

from datetime import datetime

import backtrader as bt


class SingleLegOptionsStrategy(bt.Strategy):
    """
    Single-option strategy: buy one option (call or put) and hold until exit condition
    or expiry. Uses data0 as the option feed; optionally data1 as underlying for signals.
    Flattens position before contract expiration if exit_before_expiry is True.
    """

    params = (
        ("exit_before_expiry", True),
        ("expiry_days_before", 1),
        ("size", 1),
    )

    def __init__(self) -> None:
        self.option_data = self.datas[0]
        self.underlying_data = self.datas[1] if len(self.datas) > 1 else None
        self.order = None
        self.expiration = getattr(self.option_data.params, "expiration", None)

    def log(self, txt: str, dt=None) -> None:
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order: bt.Order) -> None:
        if order.status in (order.Completed, order.Canceled, order.Margin):
            self.order = None

    def _is_expired_or_near(self) -> bool:
        if not self.params.exit_before_expiry or not self.expiration:
            return False
        cur = self.option_data.datetime.datetime(0)
        if isinstance(self.expiration, datetime):
            exp = self.expiration
        else:
            try:
                exp = datetime.strptime(str(self.expiration)[:10], "%Y-%m-%d")
            except Exception:
                return False
        cur_date = cur.date() if hasattr(cur, "date") else cur
        exp_date = exp.date() if hasattr(exp, "date") else exp
        delta = (exp_date - cur_date).days if hasattr(exp_date, "__sub__") else 0
        return delta <= self.params.expiry_days_before

    def next(self) -> None:
        if self.order:
            return
        pos = self.position
        # Flatten before expiry if we hold a position
        if pos and self._is_expired_or_near():
            self.close(data=self.option_data)
            self.log("CLOSE (before expiry)")
            return
        # Entry: simple long on first bar if no position (demo logic)
        if not pos and len(self) == 1:
            self.order = self.buy(data=self.option_data, size=self.params.size)
            self.log(f"BUY CREATE size={self.params.size}")
