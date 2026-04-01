#!/usr/bin/env python3
"""
E*TRADE trading: list accounts, list/cancel orders, place equity or option orders.
Usage:
  python scripts/etrade_trade.py list-accounts
  python scripts/etrade_trade.py list-orders --account-id-key KEY [--status OPEN]
  python scripts/etrade_trade.py cancel --account-id-key KEY --order-id 12345
  python scripts/etrade_trade.py buy-equity --account-id-key KEY --symbol AAPL --quantity 10 [--limit 150.00]
  python scripts/etrade_trade.py sell-equity --account-id-key KEY --symbol AAPL --quantity 5
  python scripts/etrade_trade.py buy-option --account-id-key KEY --symbol AAPL --call --expiry 2025-01-17 --strike 200 --quantity 1
  python scripts/etrade_trade.py sell-option --account-id-key KEY --symbol AAPL --put --expiry 2025-01-17 --strike 190 --quantity 1
"""

import argparse
import json
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from brokers import (  # noqa: E402
    etrade_list_accounts,
    etrade_list_orders,
    etrade_cancel_order,
    etrade_place_equity_order,
    etrade_place_option_order,
)


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_list_accounts() -> int:
    r = etrade_list_accounts()
    _print_json(r)
    return 0


def cmd_list_orders(args) -> int:
    r = etrade_list_orders(
        account_id_key=args.account_id_key,
        count=args.count,
        status=args.status,
        resp_format="json",
    )
    _print_json(r)
    return 0


def cmd_cancel(args) -> int:
    r = etrade_cancel_order(args.account_id_key, args.order_id, resp_format="json")
    _print_json(r)
    return 0


def cmd_buy_equity(args) -> int:
    r = etrade_place_equity_order(
        account_id_key=args.account_id_key,
        symbol=args.symbol.upper(),
        order_action="BUY",
        quantity=args.quantity,
        price_type="LIMIT" if args.limit else "MARKET",
        limit_price=args.limit,
    )
    _print_json(r)
    return 0


def cmd_sell_equity(args) -> int:
    r = etrade_place_equity_order(
        account_id_key=args.account_id_key,
        symbol=args.symbol.upper(),
        order_action="SELL",
        quantity=args.quantity,
        price_type="LIMIT" if args.limit else "MARKET",
        limit_price=args.limit,
    )
    _print_json(r)
    return 0


def cmd_buy_option(args) -> int:
    call_put = "CALL" if args.call else "PUT"
    r = etrade_place_option_order(
        account_id_key=args.account_id_key,
        symbol=args.symbol.upper(),
        call_put=call_put,
        expiry_date=args.expiry,
        strike_price=args.strike,
        order_action="BUY_OPEN",
        quantity=args.quantity,
        price_type="LIMIT" if args.limit else "MARKET",
        limit_price=args.limit,
    )
    _print_json(r)
    return 0


def cmd_sell_option(args) -> int:
    call_put = "CALL" if args.call else "PUT"
    r = etrade_place_option_order(
        account_id_key=args.account_id_key,
        symbol=args.symbol.upper(),
        call_put=call_put,
        expiry_date=args.expiry,
        strike_price=args.strike,
        order_action="SELL_CLOSE",
        quantity=args.quantity,
        price_type="LIMIT" if args.limit else "MARKET",
        limit_price=args.limit,
    )
    _print_json(r)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="E*TRADE trading CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-accounts")

    p = sub.add_parser("list-orders")
    p.add_argument("--account-id-key", required=True, help="Account ID key from list-accounts")
    p.add_argument("--count", type=int, default=25)
    p.add_argument("--status", default=None, help="OPEN, EXECUTED, CANCELLED, etc.")

    p = sub.add_parser("cancel")
    p.add_argument("--account-id-key", required=True)
    p.add_argument("--order-id", type=int, required=True)

    p = sub.add_parser("buy-equity")
    p.add_argument("--account-id-key", required=True)
    p.add_argument("--symbol", required=True)
    p.add_argument("--quantity", type=int, required=True)
    p.add_argument("--limit", type=float, default=None)

    p = sub.add_parser("sell-equity")
    p.add_argument("--account-id-key", required=True)
    p.add_argument("--symbol", required=True)
    p.add_argument("--quantity", type=int, required=True)
    p.add_argument("--limit", type=float, default=None)

    p = sub.add_parser("buy-option")
    p.add_argument("--account-id-key", required=True)
    p.add_argument("--symbol", required=True)
    p.add_argument("--call", action="store_true")
    p.add_argument("--put", action="store_true")
    p.add_argument("--expiry", required=True, help="YYYY-MM-DD")
    p.add_argument("--strike", type=float, required=True)
    p.add_argument("--quantity", type=int, required=True)
    p.add_argument("--limit", type=float, default=None)

    p = sub.add_parser("sell-option")
    p.add_argument("--account-id-key", required=True)
    p.add_argument("--symbol", required=True)
    p.add_argument("--call", action="store_true")
    p.add_argument("--put", action="store_true")
    p.add_argument("--expiry", required=True, help="YYYY-MM-DD")
    p.add_argument("--strike", type=float, required=True)
    p.add_argument("--quantity", type=int, required=True)
    p.add_argument("--limit", type=float, default=None)

    args = parser.parse_args()

    handlers = {
        "list-accounts": cmd_list_accounts,
        "list-orders": lambda: cmd_list_orders(args),
        "cancel": lambda: cmd_cancel(args),
        "buy-equity": lambda: cmd_buy_equity(args),
        "sell-equity": lambda: cmd_sell_equity(args),
        "buy-option": lambda: cmd_buy_option(args),
        "sell-option": lambda: cmd_sell_option(args),
    }
    if args.command == "buy-option" or args.command == "sell-option":
        if not args.call and not args.put:
            print("Specify --call or --put", file=sys.stderr)
            return 1
        if args.call and args.put:
            print("Specify only one of --call or --put", file=sys.stderr)
            return 1

    return handlers[args.command]()


if __name__ == "__main__":
    sys.exit(main())
