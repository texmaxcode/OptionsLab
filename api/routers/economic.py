"""Economic data proxy API: FRED, BLS, BEA.

This routes external macro data sources through the backend so the frontend
does not need to deal with multiple auth schemes or response formats.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api import auth_utils
from api.schemas import (
    EconomicSeriesResponse,
    EconomicSeriesPoint,
    StoredEconomicSeriesDeleteResponse,
    StoredEconomicSeriesInfo,
    StoredEconomicSeriesListResponse,
)
from api.utils import parse_iso_date
from config.settings import get_fred_api_key, get_bls_api_key, get_bea_api_key
from models.sql_models import UserModel, EconomicSeriesModel, EconomicSeriesPointModel
from storage.economic_repositories import EconomicSeriesRepository
from storage.session import create_all_tables, get_session_factory, session_scope


router = APIRouter(prefix="/economic", tags=["economic"])


_HTTP_TIMEOUT = 20.0
async def _fetch_json(url: str, params: dict[str, Any] | None = None, method: str = "GET", json_body: Any | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            if method == "POST":
                r = await client.post(url, params=params, json=json_body)
            else:
                r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()
    except httpx.TimeoutException as e:
        # Distinguish upstream timeouts so the UI can show a clearer message.
        raise HTTPException(
            status_code=504,
            detail=f"Timeout while fetching data from {url}. The upstream API may be slow or unreachable.",
        ) from e
    except httpx.HTTPStatusError as e:
        # Include a small snippet of the upstream response body to help debug API issues.
        body_snippet = e.response.text[:200] if e.response is not None else ""
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Upstream error from {url}: {e} {body_snippet}",
        ) from e
    except Exception as e:  # pragma: no cover - defensive
        err_type = type(e).__name__
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch data from {url} ({err_type}: {e!r})",
        ) from e


def _resolve_setting(settings: dict[str, Any], key: str, fallback: str | None) -> str | None:
    val = settings.get(key)
    if isinstance(val, str) and val.strip():
        return val
    return fallback


def _store_series_points(source: str, series_id: str, points: list[dict[str, Any]]) -> None:
    """Persist series points into the local DB (best-effort)."""
    if not points:
        return
    try:
        create_all_tables()
        with session_scope() as session:
            repo = EconomicSeriesRepository(session)
            series = repo.get_or_create_series(source=source, series_id=series_id)
            repo.upsert_points(series, points)
    except Exception:
        # Storage should not break the live fetch path.
        return


@router.get("/series", response_model=EconomicSeriesResponse)
async def get_economic_series(
    source: str = Query(..., description="Data source: fred, bls, bea"),
    series_id: str = Query(..., description="Source-specific series identifier"),
    start_date: str | None = Query(None, description="Start date YYYY-MM-DD (if supported)"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD (if supported)"),
    current_user: UserModel = Depends(auth_utils.get_current_user),
) -> EconomicSeriesResponse:
    """
    Fetch an economic time series from one of the configured providers and normalize it to (date, value).

    - fred: series_id like GDP, CPIAUCSL, UNRATE
    - bls: series_id like CUUR0000SA0, LNS14000000
    - bea: series_id is BEA TableName (e.g. T10101 for GDP table)
    """
    src = source.lower()
    start_dt = parse_iso_date(start_date)
    end_dt = parse_iso_date(end_date)

    try:
        user_settings = (
            json.loads(current_user.settings_json) if current_user.settings_json else {}
        )
    except json.JSONDecodeError:
        user_settings = {}

    if src == "fred":
        api_key = _resolve_setting(user_settings, "fred_api_key", get_fred_api_key())
        if not api_key:
            raise HTTPException(status_code=400, detail="FRED_API_KEY not configured in environment.")
        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
        }
        if start_dt:
            params["observation_start"] = start_dt.strftime("%Y-%m-%d")
        if end_dt:
            params["observation_end"] = end_dt.strftime("%Y-%m-%d")
        data = await _fetch_json("https://api.stlouisfed.org/fred/series/observations", params=params)
        observations = data.get("observations", [])
        points = [
            {"date": o.get("date"), "value": float(o["value"]) if o.get("value") not in (None, ".", "") else None}
            for o in observations
            if o.get("date")
        ]
        _store_series_points("fred", series_id, points)
        return EconomicSeriesResponse(source="fred", series_id=series_id, points=points, raw=data)

    if src == "bls":
        api_key = _resolve_setting(user_settings, "bls_api_key", get_bls_api_key())
        if not api_key:
            raise HTTPException(status_code=400, detail="BLS_API_KEY not configured in environment.")
        # BLS expects years; default to a 10-year window if dates not provided.
        if start_dt and end_dt:
            start_year = start_dt.year
            end_year = end_dt.year
        else:
            today = datetime.now(UTC)
            end_year = today.year
            start_year = end_year - 10
        body = {
            "seriesid": [series_id],
            "startyear": str(start_year),
            "endyear": str(end_year),
            "registrationKey": api_key,
        }
        data = await _fetch_json("https://api.bls.gov/publicAPI/v2/timeseries/data/", method="POST", json_body=body)
        results = data.get("Results", {}).get("series", [])
        points: list[dict[str, Any]] = []
        if results:
            for item in results[0].get("data", []):
                year = item.get("year")
                period = item.get("period")  # e.g. M01
                value = item.get("value")
                if not (year and period):
                    continue
                if not period.startswith("M"):
                    # Skip non-monthly (e.g. M13 = annual average) for simplicity
                    continue
                # Some BLS points use '-' or other non-numeric placeholders; treat as missing.
                try:
                    val = float(value) if value not in (None, "", "-") else None
                except (TypeError, ValueError):
                    val = None
                month = int(period[1:])
                date_str = f"{year}-{month:02d}-01"
                points.append({"date": date_str, "value": val})
        _store_series_points("bls", series_id, points)
        return EconomicSeriesResponse(source="bls", series_id=series_id, points=points, raw=data)

    if src == "bea":
        api_key = _resolve_setting(user_settings, "bea_api_key", get_bea_api_key())
        if not api_key:
            raise HTTPException(status_code=400, detail="BEA_API_KEY not configured in environment.")
        # Interpret series_id as TableName for NIPA dataset by default.
        params = {
            "UserID": api_key,
            "Method": "GetData",
            "datasetname": "NIPA",
            "TableName": series_id,
            "Frequency": "Q",
            "Year": "ALL",
            "ResultFormat": "JSON",
        }
        data = await _fetch_json("https://apps.bea.gov/api/data", params=params)
        # Data is nested: BEAAPI -> Results -> Data
        records = data.get("BEAAPI", {}).get("Results", {}).get("Data", [])
        points: list[dict[str, Any]] = []
        for rec in records:
            time_period = rec.get("TimePeriod")
            raw_value = rec.get("DataValue")
            if not time_period:
                continue
            # TimePeriod like "2023Q1" or "2023"
            if "Q" in time_period:
                year_str, quarter_str = time_period.split("Q", 1)
                year = int(year_str)
                quarter = int(quarter_str)
                month = (quarter - 1) * 3 + 1
                date_str = f"{year}-{month:02d}-01"
            else:
                date_str = f"{time_period}-01-01"
            # BEA uses strings like "1,234.5", "NA", "(NA)", or ".." for missing.
            if raw_value is None:
                val: float | None = None
            else:
                s = str(raw_value).strip()
                if s in ("", "NA", "(NA)", ".."):
                    val = None
                else:
                    # Strip commas and any trailing footnote text.
                    cleaned = s.replace(",", "").split()[0]
                    try:
                        val = float(cleaned)
                    except ValueError:
                        val = None
            points.append({"date": date_str, "value": val})
        _store_series_points("bea", series_id, points)
        return EconomicSeriesResponse(source="bea", series_id=series_id, points=points, raw=data)

    raise HTTPException(status_code=400, detail=f"Unsupported economic data source: {source}")


@router.get("/stored", response_model=EconomicSeriesResponse)
async def get_stored_economic_series(
    source: str = Query(..., description="Data source: fred, bls, bea"),
    series_id: str = Query(..., description="Source-specific series identifier"),
) -> EconomicSeriesResponse:
    """Return stored macro series from the local database (if present)."""
    src = source.lower()
    session_factory = get_session_factory()
    session: Session = session_factory()
    try:
        series_stmt = select(EconomicSeriesModel).where(
            EconomicSeriesModel.source == src,
            EconomicSeriesModel.series_id == series_id,
        )
        series = session.execute(series_stmt).scalars().one_or_none()
        if not series:
            raise HTTPException(
                status_code=404,
                detail=f"No stored series found for {src}:{series_id}. "
                "Run scripts/sync_economic.py --to-db to populate data.",
            )
        points_stmt = (
            select(EconomicSeriesPointModel)
            .where(EconomicSeriesPointModel.series_id_fk == series.id)
            .order_by(EconomicSeriesPointModel.date)
        )
        db_points = list(session.execute(points_stmt).scalars().all())
        points: list[EconomicSeriesPoint] = [
            EconomicSeriesPoint(date=ep.date.strftime("%Y-%m-%d"), value=ep.value)
            for ep in db_points
        ]
        return EconomicSeriesResponse(
            source=series.source,
            series_id=series.series_id,
            points=points,
            raw=None,
        )
    finally:
        session.close()


@router.delete("/stored", response_model=StoredEconomicSeriesDeleteResponse)
async def delete_stored_economic_series(
    source: str = Query(..., description="Data source: fred, bls, bea"),
    series_id: str = Query(..., description="Source-specific series identifier"),
) -> StoredEconomicSeriesDeleteResponse:
    """Delete one stored macro series and all of its points from the local database."""
    src = source.lower()
    create_all_tables()
    deleted_points = 0
    deleted_series = False
    with session_scope() as session:
        series = (
            session.execute(
                select(EconomicSeriesModel).where(
                    EconomicSeriesModel.source == src,
                    EconomicSeriesModel.series_id == series_id,
                )
            )
            .scalars()
            .one_or_none()
        )
        if not series:
            raise HTTPException(status_code=404, detail=f"No stored series found for {src}:{series_id}.")

        deleted_points = (
            session.query(EconomicSeriesPointModel)
            .filter(EconomicSeriesPointModel.series_id_fk == series.id)
            .delete(synchronize_session=False)
        )
        session.delete(series)
        deleted_series = True

    return StoredEconomicSeriesDeleteResponse(
        source=src,
        series_id=series_id,
        deleted_series=deleted_series,
        deleted_points=int(deleted_points or 0),
    )


@router.get("/stored/list", response_model=StoredEconomicSeriesListResponse)
async def list_stored_economic_series() -> StoredEconomicSeriesListResponse:
    """List all macro series currently stored in the local database."""
    session_factory = get_session_factory()
    session: Session = session_factory()
    try:
        stmt = (
            select(
                EconomicSeriesModel.source,
                EconomicSeriesModel.series_id,
                EconomicSeriesModel.label,
                func.count(EconomicSeriesPointModel.id),
                func.min(EconomicSeriesPointModel.date),
                func.max(EconomicSeriesPointModel.date),
            )
            .select_from(EconomicSeriesModel)
            .join(
                EconomicSeriesPointModel,
                EconomicSeriesPointModel.series_id_fk == EconomicSeriesModel.id,
                isouter=True,
            )
            .group_by(EconomicSeriesModel.id)
            .order_by(EconomicSeriesModel.source, EconomicSeriesModel.series_id)
        )
        rows = list(session.execute(stmt).all())
        items: list[StoredEconomicSeriesInfo] = []
        for source, series_id, label, count, min_dt, max_dt in rows:
            last_value: float | None = None
            if max_dt is not None:
                last_value_stmt = (
                    select(EconomicSeriesPointModel.value)
                    .join(
                        EconomicSeriesModel,
                        EconomicSeriesPointModel.series_id_fk == EconomicSeriesModel.id,
                    )
                    .where(EconomicSeriesModel.source == source)
                    .where(EconomicSeriesModel.series_id == series_id)
                    .where(EconomicSeriesPointModel.date == max_dt)
                    .limit(1)
                )
                last_value = session.execute(last_value_stmt).scalar_one_or_none()
            items.append(
                StoredEconomicSeriesInfo(
                    source=source,
                    series_id=series_id,
                    label=label,
                    point_count=int(count or 0),
                    first_date=min_dt.strftime("%Y-%m-%d") if min_dt else None,
                    last_date=max_dt.strftime("%Y-%m-%d") if max_dt else None,
                    last_value=last_value,
                )
            )
        return StoredEconomicSeriesListResponse(items=items)
    finally:
        session.close()


@router.get("/stored/latest", response_model=StoredEconomicSeriesListResponse)
async def latest_stored_economic_series(
    limit: int = Query(6, ge=1, le=24, description="Max number of series to return"),
) -> StoredEconomicSeriesListResponse:
    """Return latest point per series (sorted by most recently updated date)."""
    session_factory = get_session_factory()
    session: Session = session_factory()
    try:
        stmt = (
            select(
                EconomicSeriesModel.source,
                EconomicSeriesModel.series_id,
                EconomicSeriesModel.label,
                func.max(EconomicSeriesPointModel.date).label("last_date"),
                func.count(EconomicSeriesPointModel.id).label("point_count"),
            )
            .select_from(EconomicSeriesModel)
            .join(
                EconomicSeriesPointModel,
                EconomicSeriesPointModel.series_id_fk == EconomicSeriesModel.id,
                isouter=False,
            )
            .group_by(EconomicSeriesModel.id)
            .order_by(func.max(EconomicSeriesPointModel.date).desc())
            .limit(limit)
        )
        rows = list(session.execute(stmt).all())
        items: list[StoredEconomicSeriesInfo] = []
        for source, series_id, label, last_dt, point_count in rows:
            last_value_stmt = (
                select(EconomicSeriesPointModel.value)
                .join(
                    EconomicSeriesModel,
                    EconomicSeriesPointModel.series_id_fk == EconomicSeriesModel.id,
                )
                .where(EconomicSeriesModel.source == source)
                .where(EconomicSeriesModel.series_id == series_id)
                .where(EconomicSeriesPointModel.date == last_dt)
                .limit(1)
            )
            last_value = session.execute(last_value_stmt).scalar_one_or_none()
            items.append(
                StoredEconomicSeriesInfo(
                    source=source,
                    series_id=series_id,
                    label=label,
                    point_count=int(point_count or 0),
                    first_date=None,
                    last_date=last_dt.strftime("%Y-%m-%d") if last_dt else None,
                    last_value=last_value,
                )
            )
        return StoredEconomicSeriesListResponse(items=items)
    finally:
        session.close()


async def _fetch_cot_text() -> str:
    url = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            r = await client.get(url)
        r.raise_for_status()
        return r.text
    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=504,
            detail=f"Timeout while fetching data from {url}. The upstream API may be slow or unreachable.",
        ) from e
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Upstream error from {url}: {e}") from e
    except Exception as e:  # pragma: no cover - defensive
        raise HTTPException(status_code=502, detail=f"Failed to fetch data from {url}: {e}") from e


def _parse_cot_text(raw: str, market_filter: str) -> list[dict[str, Any]]:
    """Parse COT weekly financial futures text file into (date, value) points.

    We approximate "value" as Dealer Net position = Dealer_Long_All - Dealer_Short_All.

    The CFTC has published FinFutWk in both headered and headerless CSV-style formats
    over time, so we support both:

    - If a header line with ``Market_and_Exchange_Names`` is present, we use it.
    - Otherwise we treat the file as a simple CSV and infer a minimal schema where:
      * column 0: Market_and_Exchange_Names
      * column 2: Report_Date_as_YYYY-MM-DD
      * columns 8 and 9 (best-effort) approximate Dealer_Positions_Long_All/Short_All.
    """
    import csv
    from io import StringIO

    lines = raw.splitlines()
    if not lines:
        return []

    points: list[dict[str, Any]] = []

    if "Market_and_Exchange_Names" in lines[0]:
        # Headered format: use DictReader with documented field names.
        f = StringIO(raw)
        reader = csv.DictReader(f, delimiter=",")
        for row in reader:
            market = (row.get("Market_and_Exchange_Names") or "").strip()
            if market_filter.lower() not in market.lower():
                continue
            date_str = (row.get("Report_Date_as_YYYY-MM-DD") or "").strip()
            if not date_str:
                continue
            try:
                dealer_long = float(row.get("Dealer_Positions_Long_All", "0") or 0)
                dealer_short = float(row.get("Dealer_Positions_Short_All", "0") or 0)
            except ValueError:
                continue
            net = dealer_long - dealer_short
            points.append({"date": date_str, "value": net})
    else:
        # Headerless format: treat each line as CSV and infer minimal columns.
        f = StringIO(raw)
        reader = csv.reader(f, delimiter=",")
        for row in reader:
            if not row:
                continue
            market = (row[0] or "").strip().strip('"')
            if market_filter.lower() not in market.lower():
                continue
            # Best-effort: third column is date (YYYY-MM-DD) based on current FinFutWk.
            try:
                date_str = (row[2] or "").strip()
            except IndexError:
                continue
            if not date_str:
                continue
            # Approximate dealer net using two mid-line columns; if parsing fails, fall back to 0.
            try:
                dealer_long = float(row[8]) if len(row) > 8 and row[8] not in ("", ".", None) else 0.0
                dealer_short = float(row[9]) if len(row) > 9 and row[9] not in ("", ".", None) else 0.0
            except ValueError:
                dealer_long, dealer_short = 0.0, 0.0
            net = dealer_long - dealer_short
            points.append({"date": date_str, "value": net})

    # Sort by date ascending
    points.sort(key=lambda p: p["date"])
    return points

