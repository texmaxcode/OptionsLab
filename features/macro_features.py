"""
Macro/economic feature loader for the forecasting pipeline.

Loads stored economic series from the database (populated by the economic data
sync routes) and joins them onto an OHLCV DataFrame by date. Since macro series
are typically monthly or quarterly, we forward-fill them to align with daily
OHLCV data.

Usage
-----
    from features.macro_features import load_macro_features, join_macro_features

    ohlcv = load_underlying_series("AAPL", "2023-01-01", "2024-01-01")
    macro_df = load_macro_features("2023-01-01", "2024-01-01")
    enriched = join_macro_features(ohlcv, macro_df)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

from storage import session_scope

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def load_macro_features(
    from_date: datetime | str | None = None,
    to_date: datetime | str | None = None,
    *,
    series_ids: list[str] | None = None,
    session: "Session | None" = None,
) -> pd.DataFrame:
    """
    Load stored economic series from the database as a wide DataFrame.

    Each series becomes a column named ``<source>_<series_id>`` (e.g.
    ``fred_GDP``, ``fred_CPIAUCSL``). Rows are indexed by date.  Missing
    values are left as NaN; call ``join_macro_features`` to forward-fill and
    merge with OHLCV.

    Args:
        from_date: Optional start date (inclusive). Naive datetime or "YYYY-MM-DD".
        to_date: Optional end date (inclusive). Naive datetime or "YYYY-MM-DD".
        series_ids: Optional allowlist of series_id values. None = all series.
        session: Optional existing SQLAlchemy session.

    Returns:
        Wide DataFrame with a DatetimeIndex and one column per series.
        Empty DataFrame if no data is found.
    """
    from models.sql_models import EconomicSeriesModel, EconomicSeriesPointModel

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
        from sqlalchemy import select

        q = (
            select(
                EconomicSeriesModel.source,
                EconomicSeriesModel.series_id,
                EconomicSeriesPointModel.date,
                EconomicSeriesPointModel.value,
            )
            .join(
                EconomicSeriesPointModel,
                EconomicSeriesPointModel.series_id_fk == EconomicSeriesModel.id,
            )
        )
        if from_dt is not None:
            q = q.where(EconomicSeriesPointModel.date >= from_dt)
        if to_dt is not None:
            q = q.where(EconomicSeriesPointModel.date <= to_dt)
        if series_ids:
            q = q.where(EconomicSeriesModel.series_id.in_(series_ids))

        rows = sess.execute(q).all()
        if not rows:
            return pd.DataFrame()

        records = [
            {"col": f"{row.source}_{row.series_id}", "date": row.date, "value": row.value}
            for row in rows
            if row.value is not None
        ]
        if not records:
            return pd.DataFrame()

        long = pd.DataFrame(records)
        long["date"] = pd.to_datetime(long["date"])
        wide = long.pivot_table(index="date", columns="col", values="value", aggfunc="last")
        wide.index.name = None
        return wide

    if session is not None:
        return _fetch(session)
    with session_scope() as sess:
        return _fetch(sess)


def join_macro_features(
    ohlcv: pd.DataFrame,
    macro: pd.DataFrame,
    *,
    fill_method: str = "ffill",
    prefix: str = "macro_",
) -> pd.DataFrame:
    """
    Join macro features onto an OHLCV DataFrame by date.

    Macro series are typically lower-frequency (monthly, quarterly). They are
    reindexed to the OHLCV index and forward-filled so that every OHLCV row
    carries the most recent available macro reading.

    Args:
        ohlcv: OHLCV DataFrame with a DatetimeIndex.
        macro: Wide macro DataFrame from ``load_macro_features``.
        fill_method: "ffill" (default) or "bfill".
        prefix: Column name prefix for macro columns.

    Returns:
        ohlcv with additional columns for each macro series. Rows with no
        macro history at all are dropped to avoid NaN-only rows.
    """
    if macro.empty or ohlcv.empty:
        return ohlcv

    macro = macro.copy()
    macro.columns = [f"{prefix}{c}" for c in macro.columns]

    # Reindex macro to OHLCV dates, then fill forward
    macro_aligned = macro.reindex(ohlcv.index, method=fill_method)

    result = ohlcv.join(macro_aligned, how="left")
    return result
