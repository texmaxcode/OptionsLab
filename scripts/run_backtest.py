#!/usr/bin/env python3
"""
Run backtest: load data from DB and run Backtrader.

Strategies:
  single_leg     - Long call/put, exit before expiry (option; optional underlying)
  sma_crossover  - Stock: buy when fast SMA > slow SMA, sell on cross below (underlying only)
  sma_rsi        - Stock: SMA crossover + RSI filter (underlying only)
  covered_call   - Long underlying + short call; exit short before expiry (option + underlying)
  protective_put - Long underlying + long put; exit put before expiry (option + underlying)

Usage:
  # Options (need contract):
  python scripts/run_backtest.py --strategy single_leg --first-contract [--from 2024-01-01] [--to 2024-12-31]
  python scripts/run_backtest.py --strategy covered_call --first-contract --underlying AAPL

  # Stock only (underlying bars):
  python scripts/run_backtest.py --strategy sma_crossover --underlying AAPL --from 2024-01-01 --to 2024-12-31
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on path
_project_root = Path(__file__).resolve().parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from api.services.run_backtest import run_backtest  # noqa: E402
from config import get_sync_default_symbol  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run backtest from DB data")
    parser.add_argument(
        "--strategy",
        choices=["single_leg", "sma_crossover", "sma_rsi", "covered_call", "protective_put"],
        default="single_leg",
        help="Strategy to run (default: single_leg)",
    )
    parser.add_argument("--contract-id", type=int, default=None, help="Options contract ID in DB")
    parser.add_argument("--contract-symbol", default=None, help="Options contract symbol")
    parser.add_argument("--underlying", default=get_sync_default_symbol(), help="Underlying symbol")
    parser.add_argument("--first-contract", action="store_true", help="Use first contract found for underlying")
    parser.add_argument("--from", dest="from_date", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--cash", type=float, default=100_000.0, help="Starting cash")
    parser.add_argument("--no-plot", action="store_true", help="Do not show plot (plot not used when using API service)")
    args = parser.parse_args()

    result = run_backtest(
        strategy=args.strategy,
        underlying=args.underlying,
        from_date=args.from_date,
        to_date=args.to_date,
        cash=args.cash,
        contract_id=args.contract_id,
        contract_symbol=args.contract_symbol,
        first_contract=args.first_contract,
        no_plot=True,
    )

    if not result["success"]:
        print(result["error"], file=sys.stderr)
        return 1
    print("Starting portfolio value:", result["start_value"])
    print("Ending portfolio value:", result["end_value"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
