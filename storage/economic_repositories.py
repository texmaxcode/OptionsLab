"""Repositories for macro / economic time series persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.sql_models import EconomicSeriesModel, EconomicSeriesPointModel


class EconomicSeriesRepository:
    """Create and query macro/economic time series and their points."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_series(
        self,
        source: str,
        series_id: str,
        label: str | None = None,
    ) -> EconomicSeriesModel:
        stmt = select(EconomicSeriesModel).where(
            EconomicSeriesModel.source == source,
            EconomicSeriesModel.series_id == series_id,
        )
        existing = self.session.execute(stmt).scalars().one_or_none()
        if existing:
            if label and existing.label != label:
                existing.label = label
            return existing
        series = EconomicSeriesModel(source=source, series_id=series_id, label=label)
        self.session.add(series)
        self.session.flush()
        return series

    def upsert_points(
        self,
        series: EconomicSeriesModel,
        points: list[dict[str, object]],
    ) -> int:
        """Insert or update points for a series based on (date, value).

        Expects each point to have keys:
        - date: ISO date string (YYYY-MM-DD)
        - value: float | None
        """
        if not points:
            return 0

        # Preload existing points for the date range to minimize queries.
        dates: list[datetime] = []
        parsed_points: list[tuple[datetime, float | None]] = []
        for p in points:
            date_str = str(p.get("date") or "").strip()
            if not date_str:
                continue
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            value = p.get("value")
            value_f: float | None
            if value is None:
                value_f = None
            else:
                try:
                    value_f = float(value)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    value_f = None
            dates.append(dt)
            parsed_points.append((dt, value_f))

        if not dates:
            return 0

        min_date = min(dates)
        max_date = max(dates)

        stmt = (
            select(EconomicSeriesPointModel)
            .where(EconomicSeriesPointModel.series_id_fk == series.id)
            .where(EconomicSeriesPointModel.date >= min_date)
            .where(EconomicSeriesPointModel.date <= max_date)
        )
        existing_points: Sequence[EconomicSeriesPointModel] = list(
            self.session.execute(stmt).scalars().all()
        )
        existing_by_date = {ep.date.date(): ep for ep in existing_points}

        upserted = 0
        for dt, value_f in parsed_points:
            key = dt.date()
            existing = existing_by_date.get(key)
            if existing:
                if existing.value != value_f:
                    existing.value = value_f
                    upserted += 1
                continue
            ep = EconomicSeriesPointModel(
                series_id_fk=series.id,
                date=dt,
                value=value_f,
            )
            self.session.add(ep)
            upserted += 1

        return upserted

