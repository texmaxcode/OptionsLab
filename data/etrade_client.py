"""E*TRADE API client wrapper for market data (quotes, option chains)."""

from typing import Any

from pyetrade.market import ETradeMarket

from config import get_etrade_credentials


def get_etrade_market(
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
    sandbox: bool | None = None,
) -> ETradeMarket:
    """Return ETradeMarket instance. Uses env vars if args not provided."""
    key, secret, token, token_secret, dev = get_etrade_credentials(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_secret=access_secret,
        sandbox=sandbox,
    )
    return ETradeMarket(
        client_key=key,
        client_secret=secret,
        resource_owner_key=token,
        resource_owner_secret=token_secret,
        dev=dev,
    )


def get_quotes(
    symbols: list[str],
    resp_format: str = "json",
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
    sandbox: bool | None = None,
) -> dict[str, Any]:
    """Get quote data for up to 25 symbols. Returns API response dict."""
    market = get_etrade_market(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_secret=access_secret,
        sandbox=sandbox,
    )
    return market.get_quote(symbols[:25], resp_format=resp_format)


def get_option_expire_dates(
    symbol: str,
    resp_format: str = "json",
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
    sandbox: bool | None = None,
) -> dict[str, Any]:
    """Get option expiration dates for a symbol. Returns API response dict."""
    market = get_etrade_market(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_secret=access_secret,
        sandbox=sandbox,
    )
    return market.get_option_expire_date(symbol, resp_format=resp_format)


def get_option_chain(
    symbol: str,
    expiry_date: str | None = None,
    chain_type: str = "callput",
    strike_price_near: int | None = None,
    no_of_strikes: int | None = None,
    resp_format: str = "json",
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_secret: str | None = None,
    sandbox: bool | None = None,
) -> dict[str, Any]:
    """
    Get option chain for symbol. expiry_date: YYYY-MM-DD or None for nearest.
    chain_type: 'call', 'put', 'callput', or 'call/put'. Returns API response dict.
    """
    import datetime as dt
    market = get_etrade_market(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_secret=access_secret,
        sandbox=sandbox,
    )
    exp = None
    if expiry_date:
        exp = dt.datetime.strptime(expiry_date[:10], "%Y-%m-%d").date()
    normalized_chain_type = "callput" if chain_type == "call/put" else chain_type
    return market.get_option_chains(
        symbol,
        exp,
        chain_type=normalized_chain_type,
        strike_price_near=strike_price_near,
        no_of_strikes=no_of_strikes,
        resp_format=resp_format,
    )
