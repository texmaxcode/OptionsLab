"""E*TRADE order API: list accounts, list/cancel/place orders."""

from typing import Any

from pyetrade.order import ETradeOrder
from pyetrade.accounts import ETradeAccounts

from config import get_etrade_credentials


def get_etrade_order(
    sandbox: bool | None = None,
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
) -> ETradeOrder:
    """Return ETradeOrder instance. Credentials from args (user settings) or env."""
    key, secret, token, token_secret, dev = get_etrade_credentials(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_secret=access_secret,
        sandbox=sandbox,
    )
    return ETradeOrder(
        client_key=key,
        client_secret=secret,
        resource_owner_key=token,
        resource_owner_secret=token_secret,
        dev=dev,
    )


def get_etrade_accounts(
    sandbox: bool | None = None,
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
) -> ETradeAccounts:
    """Return ETradeAccounts instance for listing accounts. Credentials from args or env."""
    key, secret, token, token_secret, dev = get_etrade_credentials(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_secret=access_secret,
        sandbox=sandbox,
    )
    return ETradeAccounts(
        client_key=key,
        client_secret=secret,
        resource_owner_key=token,
        resource_owner_secret=token_secret,
        dev=dev,
    )


def etrade_list_accounts(
    resp_format: str = "json",
    sandbox: bool | None = None,
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
) -> dict[str, Any]:
    """List E*TRADE accounts. Returns API response dict. Optional creds override env."""
    accounts = get_etrade_accounts(
        sandbox=sandbox,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_secret=access_secret,
    )
    return accounts.list_accounts(resp_format=resp_format)


def etrade_get_account_balance(
    account_id_key: str,
    account_type: str | None = None,
    real_time: bool = True,
    resp_format: str = "json",
    sandbox: bool | None = None,
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
) -> dict[str, Any]:
    """Get E*TRADE account balance/details for a specific account."""
    accounts = get_etrade_accounts(
        sandbox=sandbox,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_secret=access_secret,
    )
    return accounts.get_account_balance(
        account_id_key=account_id_key,
        account_type=account_type,
        real_time=real_time,
        resp_format=resp_format,
    )


def etrade_list_orders(
    account_id_key: str,
    count: int = 25,
    status: str | None = None,
    from_date: Any = None,
    to_date: Any = None,
    resp_format: str = "json",
    sandbox: bool | None = None,
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
) -> dict[str, Any]:
    """List orders for account. status: OPEN, EXECUTED, CANCELLED, etc."""
    order = get_etrade_order(
        sandbox=sandbox,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_secret=access_secret,
    )
    return order.list_orders(
        account_id_key=account_id_key,
        count=min(count, 100),
        status=status,
        from_date=from_date,
        to_date=to_date,
        resp_format=resp_format,
    )


def etrade_cancel_order(
    account_id_key: str,
    order_id: int,
    resp_format: str = "json",
    sandbox: bool | None = None,
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
) -> dict[str, Any]:
    """Cancel an order. order_id from list_orders."""
    order = get_etrade_order(
        sandbox=sandbox,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_secret=access_secret,
    )
    return order.cancel_order(account_id_key=account_id_key, order_num=order_id, resp_format=resp_format)


def etrade_place_equity_order(
    account_id_key: str,
    symbol: str,
    order_action: str,
    quantity: int,
    price_type: str = "MARKET",
    limit_price: float | None = None,
    stop_price: float | None = None,
    order_term: str = "GOOD_UNTIL_CANCEL",
    market_session: str = "REGULAR",
    client_order_id: str | None = None,
    sandbox: bool | None = None,
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
) -> dict[str, Any]:
    """
    Place equity order. order_action: BUY, SELL, BUY_TO_COVER, SELL_SHORT.
    price_type: MARKET, LIMIT, STOP, STOP_LIMIT. For LIMIT/STOP set limit_price/stop_price.
    client_order_id: unique per account (auto-generated if None).
    """
    import uuid
    order = get_etrade_order(
        sandbox=sandbox,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_secret=access_secret,
    )
    kwargs = {
        "accountIdKey": account_id_key,
        "symbol": symbol,
        "orderAction": order_action,
        "quantity": quantity,
        "priceType": price_type,
        "orderTerm": order_term,
        "marketSession": market_session,
        "clientOrderId": client_order_id or str(uuid.uuid4())[:20],
    }
    if limit_price is not None:
        kwargs["limitPrice"] = limit_price
    if stop_price is not None:
        kwargs["stopPrice"] = stop_price
    return order.place_equity_order(**kwargs)


def etrade_place_option_order(
    account_id_key: str,
    symbol: str,
    call_put: str,
    expiry_date: str,
    strike_price: float,
    order_action: str,
    quantity: int,
    price_type: str = "MARKET",
    limit_price: float | None = None,
    order_term: str = "GOOD_UNTIL_CANCEL",
    market_session: str = "REGULAR",
    client_order_id: str | None = None,
    sandbox: bool | None = None,
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
) -> dict[str, Any]:
    """
    Place single-leg option order. symbol: underlying (e.g. AAPL).
    call_put: CALL or PUT. expiry_date: YYYY-MM-DD. order_action: BUY_OPEN, SELL_CLOSE, etc.
    """
    import uuid
    order = get_etrade_order(
        sandbox=sandbox,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_secret=access_secret,
    )
    kwargs = {
        "accountIdKey": account_id_key,
        "symbol": symbol,
        "callPut": call_put.upper(),
        "expiryDate": expiry_date[:10],
        "strikePrice": strike_price,
        "orderAction": order_action,
        "quantity": quantity,
        "priceType": price_type,
        "orderTerm": order_term,
        "marketSession": market_session,
        "clientOrderId": client_order_id or str(uuid.uuid4())[:20],
    }
    if limit_price is not None:
        kwargs["limitPrice"] = limit_price
    return order.place_option_order(**kwargs)
