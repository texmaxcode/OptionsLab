from __future__ import annotations

from datetime import date
from typing import Any

import backtrader as bt


class TradeListAnalyzer(bt.Analyzer):
    """
    Collect a flat list of closed trades with basic fields that are easy to expose via the API.

    Each trade dict contains:
    - entry_date / exit_date: ISO dates
    - direction: \"long\" or \"short\"
    - size: position size (positive for long, negative for short)
    - entry_price / exit_price
    - pnl: PnL in account currency
    - pnl_pct: PnL as % of notional at entry
    - duration_days: holding period in days
    """

    def start(self) -> None:
        self._trades: list[dict[str, Any]] = []

    def notify_trade(self, trade: bt.Trade) -> None:
        # Only record closed trades
        if not trade.isclosed:
            return

        entry_dt = bt.num2date(trade.dtopen)
        exit_dt = bt.num2date(trade.dtclose)

        entry_date: date = entry_dt.date()
        exit_date: date = exit_dt.date()

        size = float(trade.size)
        direction = "long" if size > 0 else "short" if size < 0 else "flat"

        entry_price = float(trade.price) if trade.price is not None else 0.0
        pnl = float(trade.pnl)

        notional = abs(size) * entry_price
        pnl_pct = (pnl / notional * 100.0) if notional > 0 else None

        # Infer exit price from PnL: pnl = (exit - entry) * size => exit = entry + pnl/size
        exit_price: float | None = None
        if size != 0:
            exit_price = entry_price + (pnl / size)

        self._trades.append(
            {
                "entry_date": entry_date.isoformat(),
                "exit_date": exit_date.isoformat(),
                "direction": direction,
                "size": size,
                "entry_price": entry_price,
                "exit_price": float(exit_price) if exit_price is not None else None,
                "pnl": pnl,
                "pnl_pct": round(pnl_pct, 4) if pnl_pct is not None else None,
                "duration_days": (exit_date - entry_date).days,
            }
        )

    def get_analysis(self) -> dict[str, Any]:
        return {"trades": self._trades}

