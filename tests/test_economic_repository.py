from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models.sql_models import Base, EconomicSeriesPointModel
from storage.economic_repositories import EconomicSeriesRepository


def _make_session() -> Session:
  """Create an in-memory SQLite session for repository tests."""
  engine = create_engine("sqlite:///:memory:", echo=False, future=True)
  Base.metadata.create_all(bind=engine)
  factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
  return factory()


def test_upsert_points_inserts_and_updates():
  session = _make_session()
  try:
    repo = EconomicSeriesRepository(session)
    series = repo.get_or_create_series(source="fred", series_id="GDP", label="Real GDP")

    inserted = repo.upsert_points(
      series,
      [
        {"date": "2020-01-01", "value": 1.0},
        {"date": "2020-04-01", "value": 2.0},
      ],
    )
    assert inserted == 2

    # Flush after first insert so subsequent upsert can see existing rows.
    session.flush()

    # Second call with one changed value should update the existing point.
    updated = repo.upsert_points(
      series,
      [
        {"date": "2020-01-01", "value": 1.5},  # update existing
      ],
    )
    assert updated == 1

    # Verify DB state: we should have the updated point plus the untouched second point.
    rows = (
      session.query(EconomicSeriesPointModel)
      .filter(EconomicSeriesPointModel.series_id_fk == series.id)
      .order_by(EconomicSeriesPointModel.date)
      .all()
    )
    assert len(rows) == 2
    dates = [r.date for r in rows]
    values = [r.value for r in rows]

    assert dates[0] == datetime(2020, 1, 1)
    assert dates[1] == datetime(2020, 4, 1)
    assert values == [1.5, 2.0]
  finally:
    session.close()

