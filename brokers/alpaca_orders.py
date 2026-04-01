"""Alpaca Trading API wrapper for paper trading account, orders, and options."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import requests

from config import get_alpaca_credentials


def _headers(api_key: str, api_secret: str) -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret,
        "Content-Type": "application/json",
    }


def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> Any:
    key, secret, base_url = get_alpaca_credentials(
        api_key=api_key,
        api_secret=api_secret,
    )
    response = requests.request(
        method,
        f"{base_url}{path}",
        headers=_headers(key, secret),
        params=params,
        json=json_body,
        timeout=30,
    )
    response.raise_for_status()
    if response.status_code == 204 or not response.text.strip():
        return None
    return response.json()


def _alpaca_order_status_param(status: str | None) -> str:
    if not status:
        return "open"
    lookup = {
        "OPEN": "open",
        "EXECUTED": "closed",
        "CANCELLED": "closed",
        "ALL": "all",
    }
    return lookup.get(status.upper(), "all")


def _matches_requested_status(order: dict[str, Any], status: str | None) -> bool:
    if not status or status.upper() == "ALL":
        return True
    value = str(order.get("status") or "").lower()
    requested = status.upper()
    if requested == "OPEN":
        return value in {
            "new",
            "accepted",
            "pending_new",
            "accepted_for_bidding",
            "partially_filled",
            "held",
            "pending_cancel",
            "pending_replace",
        }
    if requested == "EXECUTED":
        return value == "filled"
    if requested == "CANCELLED":
        return value in {"canceled", "cancelled", "expired"}
    return value == requested.lower()


def _alpaca_side(order_action: str) -> str:
    action = (order_action or "").upper()
    if action in {"BUY", "BUY_OPEN", "BUY_CLOSE", "BUY_TO_COVER"}:
        return "buy"
    if action in {"SELL", "SELL_OPEN", "SELL_CLOSE", "SELL_SHORT"}:
        return "sell"
    raise ValueError(f"Unsupported Alpaca order action: {order_action}")


def _alpaca_type(price_type: str) -> str:
    kind = (price_type or "MARKET").upper()
    mapping = {
        "MARKET": "market",
        "LIMIT": "limit",
        "STOP": "stop",
        "STOP_LIMIT": "stop_limit",
    }
    if kind not in mapping:
        raise ValueError(f"Unsupported Alpaca price type: {price_type}")
    return mapping[kind]


def _occ_option_symbol(
    symbol: str,
    call_put: str,
    expiry_date: str,
    strike_price: float,
) -> str:
    expiry = datetime.strptime(expiry_date[:10], "%Y-%m-%d")
    cp = "C" if call_put.upper().startswith("C") else "P"
    strike = (
        Decimal(str(strike_price))
        .quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        * Decimal("1000")
    )
    return f"{symbol.strip().upper()}{expiry.strftime('%y%m%d')}{cp}{int(strike):08d}"


def alpaca_get_account(
    api_key: str | None = None,
    api_secret: str | None = None,
) -> dict[str, Any]:
    return _request(
        "GET",
        "/v2/account",
        api_key=api_key,
        api_secret=api_secret,
    )


def alpaca_list_orders(
    count: int = 25,
    status: str | None = None,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> list[dict[str, Any]]:
    orders = _request(
        "GET",
        "/v2/orders",
        params={
            "status": _alpaca_order_status_param(status),
            "limit": min(max(count, 1), 100),
            "direction": "desc",
            "nested": "false",
        },
        api_key=api_key,
        api_secret=api_secret,
    )
    if not isinstance(orders, list):
        return []
    return [o for o in orders if isinstance(o, dict) and _matches_requested_status(o, status)]


def alpaca_cancel_order(
    order_id: str,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> None:
    _request(
        "DELETE",
        f"/v2/orders/{order_id}",
        api_key=api_key,
        api_secret=api_secret,
    )


def alpaca_place_equity_order(
    symbol: str,
    order_action: str,
    quantity: int,
    price_type: str = "MARKET",
    limit_price: float | None = None,
    stop_price: float | None = None,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> dict[str, Any]:
    order_type = _alpaca_type(price_type)
    payload: dict[str, Any] = {
        "symbol": symbol.strip().upper(),
        "qty": quantity,
        "side": _alpaca_side(order_action),
        "type": order_type,
        "time_in_force": "day",
    }
    if order_type in {"limit", "stop_limit"}:
        if limit_price is None:
            raise ValueError("limit_price is required for LIMIT and STOP_LIMIT Alpaca orders.")
        payload["limit_price"] = limit_price
    if order_type in {"stop", "stop_limit"}:
        if stop_price is None:
            raise ValueError("stop_price is required for STOP and STOP_LIMIT Alpaca orders.")
        payload["stop_price"] = stop_price
    return _request(
        "POST",
        "/v2/orders",
        json_body=payload,
        api_key=api_key,
        api_secret=api_secret,
    )


def alpaca_place_option_order(
    symbol: str,
    call_put: str,
    expiry_date: str,
    strike_price: float,
    order_action: str,
    quantity: int,
    price_type: str = "MARKET",
    limit_price: float | None = None,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> dict[str, Any]:
    option_symbol = _occ_option_symbol(symbol, call_put, expiry_date, strike_price)
    return alpaca_place_equity_order(
        option_symbol,
        order_action=order_action,
        quantity=quantity,
        price_type=price_type,
        limit_price=limit_price,
        api_key=api_key,
        api_secret=api_secret,
    )
