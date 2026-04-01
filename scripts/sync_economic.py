"""Sync macro / economic time series via the API and store to CSV or DB.

Usage (from project root, with API running on localhost:8000):

    PYTHONPATH=. ./venv/bin/python3 scripts/sync_economic.py \\
        --source fred --series-id GDP --from 2015-01-01 --to 2024-12-31 \\
        --output data/fred_GDP_2015_2024.csv

By default it calls the backend `/economic/series` endpoint on
`TRADING_API_URL` (default: http://localhost:8000) and writes a CSV file with
columns `date,value`.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any

import httpx

from storage.session import session_scope, create_all_tables
from storage.economic_repositories import EconomicSeriesRepository


PRESETS: dict[str, list[str]] = {
    "fred": ["GDP", "CPIAUCSL", "UNRATE", "IPMAN", "DGS10", "DEXUSEU", "VIXCLS"],
    "bls": ["CUUR0000SA0", "LNS14000000"],
    "bea": ["T10101"],
}


def fetch_series(
    source: str,
    series_id: str,
    start_date: str | None,
    end_date: str | None,
) -> list[dict[str, Any]]:
    base_url = os.environ.get("TRADING_API_URL", "http://localhost:8000")
    url = f"{base_url.rstrip('/')}/economic/series"
    params: dict[str, str] = {
        "source": source,
        "series_id": series_id,
    }
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    with httpx.Client(timeout=30.0) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    points = data.get("points", [])
    if not isinstance(points, list):
        raise RuntimeError("Unexpected response format: 'points' is not a list")
    return points


def write_csv(points: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "value"])
        for p in points:
            writer.writerow([p.get("date"), p.get("value")])


def write_db(
    source: str,
    series_id: str,
    points: list[dict[str, Any]],
) -> int:
    """Persist series metadata and points into the trading database."""
    # Ensure tables exist (no-op if already created).
    create_all_tables()
    with session_scope() as session:
        repo = EconomicSeriesRepository(session)
        series = repo.get_or_create_series(source=source, series_id=series_id)
        upserted = repo.upsert_points(series, points)
    return upserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync macro/economic time-series via API to CSV.")
    parser.add_argument(
        "--all-presets",
        action="store_true",
        help="Import all preset series across all sources (FRED/BLS/BEA).",
    )
    parser.add_argument("--source", help="Source: fred, bls, bea")
    parser.add_argument("--series-id", help="Series identifier / code")
    parser.add_argument("--from", dest="from_date", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", default=None, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--output",
        help="Output CSV path. Default: economic_{source}_{series_id}.csv in current directory.",
    )
    parser.add_argument(
        "--to-db",
        action="store_true",
        help="Store series into the trading database instead of (or in addition to) CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="When using --all-presets, write one CSV per series into this directory (default: ./data/economic).",
    )
    args = parser.parse_args()

    from_date = args.from_date
    to_date = args.to_date

    if args.all_presets:
        out_dir = Path(args.output_dir or "data/economic")
        total = sum(len(v) for v in PRESETS.values())
        done = 0
        failures = 0
        for src, ids in PRESETS.items():
            for sid in ids:
                done += 1
                try:
                    pts = fetch_series(src, sid, from_date, to_date)
                    if args.to_db:
                        upserted = write_db(src, sid, pts)
                        print(f"[{done}/{total}] {src}:{sid} upserted {upserted} points into DB")
                    # Write one CSV per series unless explicitly suppressed by --to-db and no output-dir
                    if args.output_dir is not None or not args.to_db:
                        fname = f"economic_{src}_{sid.replace(' ', '_').replace('/', '_')}.csv"
                        write_csv(pts, out_dir / fname)
                        print(f"[{done}/{total}] {src}:{sid} wrote {len(pts)} points to {out_dir / fname}")
                except Exception as e:
                    failures += 1
                    print(f"[{done}/{total}] {src}:{sid} FAILED: {e}")
        if failures:
            raise SystemExit(f"{failures} series failed.")
        return

    source = args.source
    series_id = args.series_id
    if not source or not series_id:
        raise SystemExit("Provide --source and --series-id, or use --all-presets.")

    points = fetch_series(source, series_id, from_date, to_date)

    if args.to_db:
        upserted = write_db(source, series_id, points)
        print(f"Upserted {upserted} points into DB for {source}:{series_id}")

    # Default behavior: still write CSV unless explicitly skipped by omitting output?
    if args.output is not None or not args.to_db:
        output = Path(
            args.output
            or f"economic_{source}_{series_id.replace(' ', '_').replace('/', '_')}.csv"
        )
        write_csv(points, output)
        print(f"Wrote {len(points)} points to {output}")


if __name__ == "__main__":
    main()

