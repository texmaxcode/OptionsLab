"""Sync underlying and options data from Massive REST API to DB (Pydantic + SQLAlchemy)."""

from datetime import datetime, timezone
from typing import Iterator

from config import get_massive_api_key
from data.massive_client import get_massive_client
from models.pydantic_models import UnderlyingBarIn
from storage import session_scope, UnderlyingBarRepository, OptionsContractRepository, OptionsBarRepository


def _ms_to_datetime(ms: int) -> datetime:
    """Convert Unix milliseconds to naive datetime (UTC)."""
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).replace(tzinfo=None)


def sync_underlying_bars(
    symbol: str,
    from_date: str,
    to_date: str,
    timespan: str = "day",
    multiplier: int = 1,
    massive_api_key: str | None = None,
) -> int:
    """
    Fetch underlying OHLCV from Massive list_aggs and persist. Returns count of bars upserted.
    massive_api_key: override from user settings; else uses MASSIVE_API_KEY env.
    """
    api_key = massive_api_key or get_massive_api_key()
    if not api_key:
        raise ValueError("MASSIVE_API_KEY not set. Configure in Settings or environment.")
    client = get_massive_client(api_key)
    count = 0
    with session_scope() as session:
        repo = UnderlyingBarRepository(session)
        for agg in client.list_aggs(symbol, multiplier, timespan, from_date, to_date, limit=50000):
            # Massive Agg: t (ms), o, h, l, c, v, n
            ts = getattr(agg, "timestamp", None) or getattr(agg, "t", None)
            if ts is None:
                continue
            dt = _ms_to_datetime(ts)
            bar = UnderlyingBarIn(
                symbol=symbol,
                datetime=dt,
                open=float(agg.open),
                high=float(agg.high),
                low=float(agg.low),
                close=float(agg.close),
                volume=int(agg.volume or 0),
            )
            repo.upsert_bar(
                bar.symbol,
                bar.datetime,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
            )
            count += 1
    return count


def _iter_option_contracts(client, underlying_asset: str, expiration_gte: str | None, strike_gte: float | None, strike_lte: float | None) -> Iterator:
    """Yield option contract snapshots from list_snapshot_options_chain with optional filters."""
    params = {}
    if expiration_gte:
        params["expiration_date.gte"] = expiration_gte
    if strike_gte is not None:
        params["strike_price.gte"] = strike_gte
    if strike_lte is not None:
        params["strike_price.lte"] = strike_lte
    return client.list_snapshot_options_chain(underlying_asset, params=params or None)


def sync_options_chain_and_bars(
    underlying_symbol: str,
    from_date: str,
    to_date: str,
    expiration_date_gte: str | None = None,
    strike_price_gte: float | None = None,
    strike_price_lte: float | None = None,
    max_contracts: int | None = None,
    timespan: str = "day",
    multiplier: int = 1,
    massive_api_key: str | None = None,
) -> tuple[int, int]:
    """
    Fetch options chain (contracts) from Massive, then bars per contract via list_aggs.
    Persists contracts and bars. Returns (contracts_processed, total_bars_upserted).
    massive_api_key: override from user settings; else uses MASSIVE_API_KEY env.
    """
    api_key = massive_api_key or get_massive_api_key()
    if not api_key:
        raise ValueError("MASSIVE_API_KEY not set. Configure in Settings or environment.")
    client = get_massive_client(api_key)
    contracts_processed = 0
    total_bars = 0
    with session_scope() as session:
        contract_repo = OptionsContractRepository(session)
        bar_repo = OptionsBarRepository(session)
        chain = _iter_option_contracts(
            client,
            underlying_symbol,
            expiration_gte=expiration_date_gte,
            strike_gte=strike_price_gte,
            strike_lte=strike_price_lte,
        )
        for snap in chain:
            if max_contracts is not None and contracts_processed >= max_contracts:
                break
            # OptionContractSnapshot: details.ticker (OCC), details.expiration_date, details.strike_price, details.contract_type (call/put)
            try:
                details = getattr(snap, "details", None)
                if not details:
                    continue
                ticker = getattr(details, "ticker", None) or getattr(snap, "ticker", None)
                if not ticker:
                    continue
                exp = getattr(details, "expiration_date", None)
                strike = getattr(details, "strike_price", None)
                ctype = getattr(details, "contract_type", None)
                if exp is None or strike is None or ctype is None:
                    continue
                if isinstance(exp, str):
                    exp_dt = datetime.strptime(exp[:10], "%Y-%m-%d")
                else:
                    exp_dt = exp
                option_type = "call" if (str(ctype).lower() in ("call", "c")) else "put"
                contract = contract_repo.get_or_create(
                    underlying_symbol=underlying_symbol,
                    expiration=exp_dt,
                    strike=float(strike),
                    option_type=option_type,
                    contract_symbol=str(ticker),
                )
                session.flush()
                contracts_processed += 1
            except Exception:
                continue
            # Fetch aggregates for this option ticker
            bar_count = 0
            try:
                for agg in client.list_aggs(ticker, multiplier, timespan, from_date, to_date, limit=50000):
                    ts = getattr(agg, "timestamp", None) or getattr(agg, "t", None)
                    if ts is None:
                        continue
                    dt = _ms_to_datetime(ts)
                    bar_repo.upsert_bar(
                        contract_id=contract.id,
                        dt=dt,
                        o=float(agg.open),
                        h=float(agg.high),
                        low=float(agg.low),
                        c=float(agg.close),
                        volume=int(agg.volume or 0),
                        open_interest=None,
                    )
                    bar_count += 1
                total_bars += bar_count
            except Exception:
                pass
    return contracts_processed, total_bars
