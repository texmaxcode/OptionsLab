#!/usr/bin/env python3
"""
Seed dummy market data so all platform features can be demonstrated without
running external imports (Massive, E*TRADE) or live sync.

Creates:
- Underlying OHLCV bars for one or more symbols (e.g. AAPL, MSFT) over a date range,
  so backtests, forecasting, strategy engine, and research/analyze have data.
- Optional: one or more options contracts and their bars so options backtests
  (single_leg, covered_call, protective_put) work with "first contract".

Uses TRADING_DATABASE_URL (default: sqlite:///trading.db). Run from project root:
  PYTHONPATH=. python scripts/seed_dummy_data.py

Options:
  --symbols AAPL,MSFT     Comma-separated symbols (default: AAPL,MSFT)
  --from 2024-01-01      Start date (default: 2024-01-01)
  --to 2024-12-31        End date (default: 2024-12-31)
  --no-options           Skip options contracts and bars
  --reset                Delete existing bars for the given symbols before seeding
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

# Allow running from project root without installing the package
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from storage import session_scope  # noqa: E402
from storage.repositories import (  # noqa: E402
    UnderlyingBarRepository,
    OptionsContractRepository,
    OptionsBarRepository,
)
from storage.session import create_all_tables  # noqa: E402

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed dummy underlying and optional options data for demos."
    )
    parser.add_argument(
        "--symbols",
        default="AAPL,MSFT",
        help="Comma-separated underlying symbols (default: AAPL,MSFT)",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        default="2024-01-01",
        metavar="DATE",
        help="Start date YYYY-MM-DD (default: 2024-01-01)",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        default="2024-12-31",
        metavar="DATE",
        help="End date YYYY-MM-DD (default: 2024-12-31)",
    )
    parser.add_argument(
        "--no-options",
        action="store_true",
        help="Do not create options contracts/bars",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing underlying bars for the given symbols before seeding",
    )
    return parser.parse_args()


def _date_range(from_str: str, to_str: str) -> list[datetime]:
    """Return list of naive datetimes at midnight, one per day in [from, to] inclusive."""
    from_dt = datetime.strptime(from_str.strip()[:10], "%Y-%m-%d")
    to_dt = datetime.strptime(to_str.strip()[:10], "%Y-%m-%d")
    if from_dt > to_dt:
        raise ValueError(f"from_date {from_str} must be <= to_date {to_str}")
    out: list[datetime] = []
    d = from_dt
    while d <= to_dt:
        out.append(d.replace(hour=0, minute=0, second=0, microsecond=0))
        d += timedelta(days=1)
    return out


def _generate_ohlcv(
    base_price: float,
    num_days: int,
    volatility: float = 0.01,
    drift: float = 0.0002,
    seed: int | None = None,
) -> list[tuple[float, float, float, float, int]]:
    """Generate deterministic OHLCV bars (open, high, low, close, volume)."""
    if seed is not None:
        random.seed(seed)
    out: list[tuple[float, float, float, float, int]] = []
    price = base_price
    for _ in range(num_days):
        ret = drift + random.gauss(0, volatility)
        open_p = price
        close_p = price * (1 + ret)
        high_p = max(open_p, close_p) * (1 + random.uniform(0, 0.005))
        low_p = min(open_p, close_p) * (1 - random.uniform(0, 0.005))
        volume = random.randint(800_000, 2_000_000)
        out.append((open_p, high_p, low_p, close_p, volume))
        price = close_p
    return out


def _occ_contract_symbol(underlying: str, expiration: datetime, option_type: str, strike: float) -> str:
    """Build OCC-style contract symbol, e.g. O:AAPL241220C00150000."""
    yy = expiration.strftime("%y")
    mm = expiration.strftime("%m")
    dd = expiration.strftime("%d")
    strike_str = f"{int(strike * 1000):08d}"
    return f"O:{underlying}{yy}{mm}{dd}{option_type[0].upper()}{strike_str}"


def seed_underlying(
    session: "Session",
    symbols: list[str],
    from_dt: str,
    to_dt: str,
    reset: bool,
) -> dict[str, int]:
    """Seed underlying bars. Returns symbol -> count inserted."""
    repo = UnderlyingBarRepository(session)
    dates = _date_range(from_dt, to_dt)
    n_days = len(dates)
    if n_days == 0:
        return {}

    counts: dict[str, int] = {}
    base_prices = {"AAPL": 185.0, "MSFT": 375.0, "GOOGL": 140.0}
    for i, symbol in enumerate(symbols):
        if reset:
            deleted = repo.delete_bars_by_symbol(symbol)
            if deleted:
                print(f"  Deleted {deleted} existing bars for {symbol}")
        base = base_prices.get(symbol, 100.0)
        bars = _generate_ohlcv(base, n_days, seed=hash(symbol) % (2**31))
        for d, (o, h, low, c, v) in zip(dates, bars, strict=True):
            repo.upsert_bar(symbol, d, o, h, low, c, v)
        counts[symbol] = n_days
    return counts


def seed_options(
    session: "Session",
    underlying: str,
    from_dt: str,
    to_dt: str,
) -> tuple[int, int]:
    """Seed one options contract and its bars. Returns (contracts_created, bars_created)."""
    contract_repo = OptionsContractRepository(session)
    bar_repo = OptionsBarRepository(session)

    to_date = datetime.strptime(to_dt.strip()[:10], "%Y-%m-%d").date()
    # Expiration near end of range (e.g. 20th of last month)
    exp_dt = datetime(to_date.year, to_date.month, min(20, to_date.day), 0, 0, 0)
    if exp_dt.date() > to_date:
        exp_dt = datetime(to_date.year, to_date.month, to_date.day, 0, 0, 0)

    strike = 150.0 if underlying == "AAPL" else 380.0
    contract_symbol = _occ_contract_symbol(underlying, exp_dt, "call", strike)
    contract = contract_repo.get_or_create(
        underlying_symbol=underlying,
        expiration=exp_dt,
        strike=strike,
        option_type="call",
        contract_symbol=contract_symbol,
    )
    session.flush()

    dates = _date_range(from_dt, to_dt)
    # Options bars only up to expiration
    option_dates = [d for d in dates if d.date() <= exp_dt.date()]
    base_option_price = 5.0
    random.seed(42)  # reproducible option prices
    for d in option_dates:
        days_left = (exp_dt.date() - d.date()).days
        price = max(0.5, base_option_price * (1 + days_left / 100) + random.gauss(0, 0.3))
        o, c = price, price + random.gauss(0, 0.2)
        h, low = max(o, c) + 0.1, min(o, c) - 0.1
        bar_repo.upsert_bar(
            contract.id,
            d,
            o, h, low, c,
            volume=random.randint(1000, 5000),
            open_interest=random.randint(5000, 20000),
        )
    return 1, len(option_dates)


def main() -> int:
    args = _parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        print("No symbols given.", file=sys.stderr)
        return 1

    try:
        _date_range(args.from_date, args.to_date)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    print("Creating tables (if needed)...")
    create_all_tables()

    with session_scope() as session:
        print("Seeding underlying bars...")
        counts = seed_underlying(
            session,
            symbols,
            args.from_date,
            args.to_date,
            reset=args.reset,
        )
        for sym, n in counts.items():
            print(f"  {sym}: {n} bars")

        if not args.no_options and symbols:
            print("Seeding options (one contract per first symbol)...")
            first = symbols[0]
            n_contracts, n_bars = seed_options(session, first, args.from_date, args.to_date)
            print(f"  Contract for {first}: {n_bars} option bars")

    print("Done. You can run backtests, forecasts, strategy engine, and research/analyze.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
