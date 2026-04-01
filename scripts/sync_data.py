#!/usr/bin/env python3
"""
Sync market data to local DB. Supports Massive.com (historical) and E*TRADE (current quotes/options).
Usage:
  # Massive (historical bars) - one or more symbols
  export MASSIVE_API_KEY=your_key
  python scripts/sync_data.py --source massive [--symbol AAPL] [--from 2024-01-01] [--to 2024-12-31]
  python scripts/sync_data.py --source massive --symbol AAPL,MSFT,GOOGL [--from 2024-01-01] [--to 2024-12-31]

  # E*TRADE (current quotes snapshot) - one or more symbols
  export ETrade_CONSUMER_KEY=... ETrade_CONSUMER_SECRET=... ETrade_ACCESS_TOKEN=... ETrade_ACCESS_SECRET=...
  python scripts/sync_data.py --source etrade [--symbol AAPL,MSFT] [--options] [--max-contracts 10]
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on path
_project_root = Path(__file__).resolve().parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import (  # noqa: E402
    get_massive_api_key,
    get_etrade_consumer_key,
    get_sync_default_symbol,
    get_sync_date_from,
    get_sync_date_to,
)
from data import (  # noqa: E402
    sync_underlying_bars,
    sync_options_chain_and_bars,
    sync_etrade_quotes,
    sync_etrade_option_chain,
)
from storage import create_all_tables  # noqa: E402

try:
    from massive.exceptions import BadResponse as MassiveBadResponse
except ImportError:
    MassiveBadResponse = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync market data to local DB (Massive or E*TRADE)")
    parser.add_argument("--source", choices=("massive", "etrade"), default="massive", help="Data source (default: massive)")
    parser.add_argument("--symbol", default=get_sync_default_symbol(), help="Underlying symbol(s), comma-separated (e.g. AAPL,MSFT,GOOGL)")
    parser.add_argument("--from", dest="from_date", default=get_sync_date_from(), help="Start date YYYY-MM-DD (Massive only)")
    parser.add_argument("--to", dest="to_date", default=get_sync_date_to(), help="End date YYYY-MM-DD (Massive only)")
    parser.add_argument("--underlying-only", action="store_true", help="Only sync underlying, not options (Massive only)")
    parser.add_argument("--options", action="store_true", help="Also sync option chain (E*TRADE only)")
    parser.add_argument("--max-contracts", type=int, default=None, help="Max option contracts to fetch")
    parser.add_argument("--expiration-gte", default=None, help="Options expiration >= YYYY-MM-DD (Massive only)")
    parser.add_argument("--expiry", default=None, help="Option expiry YYYY-MM-DD for chain (E*TRADE only)")
    parser.add_argument("--strike-gte", type=float, default=None, help="Options strike >= value")
    parser.add_argument("--strike-lte", type=float, default=None, help="Options strike <= value")
    args = parser.parse_args()

    create_all_tables()

    if args.source == "massive":
        if not get_massive_api_key():
            print("Error: MASSIVE_API_KEY not set.", file=sys.stderr)
            return 1
        symbols = [s.strip() for s in args.symbol.split(",") if s.strip()]
        if not symbols:
            symbols = [get_sync_default_symbol()]
        from_date = args.from_date
        to_date = args.to_date
        total_bars = 0
        for symbol in symbols:
            print(f"Syncing underlying {symbol} from {from_date} to {to_date} (Massive)...")
            n = sync_underlying_bars(symbol, from_date, to_date)
            total_bars += n
            print(f"  {symbol}: underlying bars upserted: {n}")
        print(f"Total underlying bars upserted: {total_bars}")
        if not args.underlying_only:
            for symbol in symbols:
                print(f"Syncing options chain and bars for {symbol}...")
                try:
                    contracts, bars = sync_options_chain_and_bars(
                        symbol, from_date, to_date,
                        expiration_date_gte=args.expiration_gte,
                        strike_price_gte=args.strike_gte,
                        strike_price_lte=args.strike_lte,
                        max_contracts=args.max_contracts,
                    )
                    print(f"  {symbol}: contracts={contracts}, bars={bars}")
                except Exception as e:
                    if MassiveBadResponse and type(e) is MassiveBadResponse:
                        print(
                            f"  {symbol}: Options sync skipped (plan may not include options). Use --underlying-only for underlying only.",
                            file=sys.stderr,
                        )
                    else:
                        raise

    else:
        if not get_etrade_consumer_key():
            print("Error: E*TRADE credentials not set (ETrade_CONSUMER_KEY, etc.).", file=sys.stderr)
            return 1
        symbols = [s.strip() for s in args.symbol.split(",") if s.strip()]
        if not symbols:
            symbols = [get_sync_default_symbol()]
        print(f"Syncing E*TRADE quotes for {symbols}...")
        n = sync_etrade_quotes(symbols)
        print(f"Underlying bars (snapshot) upserted: {n}")
        if args.options:
            for sym in symbols:
                print(f"Syncing E*TRADE option chain for {sym}...")
                contracts, bars = sync_etrade_option_chain(sym, expiry_date=args.expiry, max_contracts=args.max_contracts)
                print(f"  {sym}: contracts={contracts}, bars={bars}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
