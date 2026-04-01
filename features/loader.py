"""
Load OHLCV series from storage for feature engineering and forecasting.

Uses the same repositories as the backtesting engine (UnderlyingBarRepository)
so that forecasts and backtests share the same data foundation.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

from backtrader_feeds import underlying_bars_to_dataframe

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from storage import session_scope
from storage.repositories import UnderlyingBarRepository


def load_underlying_series(
    symbol: str,
    from_date: datetime | str | None = None,
    to_date: datetime | str | None = None,
    *,
    session: "Session | None" = None,
) -> pd.DataFrame:
    """
    Load underlying OHLCV bars for a symbol into a pandas DataFrame.

    Uses the same storage and date range semantics as the backtesting engine.
    Datetime index, columns: open, high, low, close, volume.

    Args:
        symbol: Underlying symbol (e.g. "AAPL").
        from_date: Start of range (inclusive). Naive datetime or "YYYY-MM-DD".
        to_date: End of range (inclusive). Naive datetime or "YYYY-MM-DD".
        session: Optional SQLAlchemy session. If None, a new session is used.

    Returns:
        DataFrame with datetime index and columns open, high, low, close, volume.
        Empty DataFrame if no bars found.
    """
    def _parse(d: datetime | str | None) -> datetime | None:
        if d is None:
            return None
        if isinstance(d, datetime):
            return d
        try:
            return datetime.strptime(str(d).strip()[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return None

    from_dt = _parse(from_date)
    to_dt = _parse(to_date)

    def _fetch(sess: "Session") -> pd.DataFrame:
        repo = UnderlyingBarRepository(sess)
        bars = list(repo.get_bars(symbol, from_date=from_dt, to_date=to_dt))
        return underlying_bars_to_dataframe(bars)

    if session is not None:
        return _fetch(session)
    with session_scope() as sess:
        return _fetch(sess)
