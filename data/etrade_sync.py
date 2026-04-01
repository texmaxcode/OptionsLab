"""Sync current quotes and option chain from E*TRADE into the local DB (snapshot as one bar per symbol/contract)."""

from datetime import datetime, timezone
from typing import Any

from config import get_etrade_consumer_key
from data.etrade_client import get_quotes, get_option_chain, get_option_expire_dates
from storage import session_scope, UnderlyingBarRepository, OptionsContractRepository, OptionsBarRepository


def _etrade_kwargs(creds: dict[str, Any] | None) -> dict[str, Any]:
    """Build kwargs for etrade_client from credentials dict (Settings) or None (use env)."""
    if not creds:
        return {}
    return {
        "consumer_key": creds.get("etrade_consumer_key"),
        "consumer_secret": creds.get("etrade_consumer_secret"),
        "access_token": creds.get("etrade_access_token"),
        "access_secret": creds.get("etrade_access_secret"),
        "sandbox": creds.get("etrade_sandbox"),
    }


def _now_normalized() -> datetime:
    """Current UTC datetime normalized to midnight for bar key (E*TRADE has no history, we store snapshot as one bar)."""
    return datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)


def _float(val: any, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _int(val: any, default: int = 0) -> int:
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def sync_etrade_quotes(
    symbols: list[str],
    etrade_credentials: dict[str, Any] | None = None,
) -> int:
    """
    Fetch current quotes for symbols from E*TRADE and persist as one underlying bar per symbol (datetime = today).
    Returns count of bars upserted.
    etrade_credentials: from user settings; else uses env vars.
    """
    kwargs = _etrade_kwargs(etrade_credentials)
    if not kwargs:
        if not get_etrade_consumer_key():
            raise ValueError("E*TRADE credentials not set. Configure in Settings or environment.")
    else:
        if not all((
            kwargs.get("consumer_key"),
            kwargs.get("consumer_secret"),
            kwargs.get("access_token"),
            kwargs.get("access_secret"),
        )):
            raise ValueError("E*TRADE credentials incomplete. Set all four in Settings.")
    resp = get_quotes(symbols, resp_format="json", **kwargs)
    count = 0
    requested_symbols = {s.strip().upper() for s in symbols if s.strip()}
    unexpected_symbols: set[str] = set()
    dt = _now_normalized()
    with session_scope() as session:
        repo = UnderlyingBarRepository(session)
        # JSON: QuoteResponse.QuoteData array or nested structure
        quote_data = resp.get("QuoteResponse", {}).get("QuoteData") or resp.get("QuoteData")
        if not quote_data:
            return 0
        quotes = quote_data if isinstance(quote_data, list) else [quote_data]
        for q in quotes:
            product = q.get("Product") or q.get("product") or {}
            sym = (
                q.get("symbol")
                or q.get("Symbol")
                or product.get("symbol")
                or product.get("Symbol")
                or ""
            ).strip()
            if not sym:
                continue
            if requested_symbols and sym.upper() not in requested_symbols:
                unexpected_symbols.add(sym.upper())
                continue
            # E*TRADE quote fields may be All or subset
            all_quote = q.get("All") or q.get("all") or q
            o = _float(all_quote.get("open") or all_quote.get("Open"), 0.0)
            h = _float(all_quote.get("high") or all_quote.get("High"), 0.0)
            l_ = _float(all_quote.get("low") or all_quote.get("Low"), 0.0)
            c = _float(all_quote.get("lastTrade") or all_quote.get("LastTrade") or all_quote.get("close") or all_quote.get("Close"), 0.0)
            v = _int(all_quote.get("volume") or all_quote.get("Volume"), 0)
            if c <= 0 and o <= 0:
                continue
            if o <= 0:
                o = c
            if h <= 0:
                h = max(o, c)
            if l_ <= 0:
                l_ = min(o, c)
            repo.upsert_bar(sym, dt, o, h, l_, c, v)
            count += 1
    if count == 0 and unexpected_symbols:
        requested_list = ", ".join(sorted(requested_symbols))
        returned_list = ", ".join(sorted(unexpected_symbols))
        sandbox_hint = (
            " E*TRADE sandbox returns canned sample market data; switch E*TRADE mode to Live for real symbols."
            if kwargs.get("sandbox")
            else ""
        )
        raise ValueError(
            f"E*TRADE returned quote data for unexpected symbol(s) {returned_list} "
            f"instead of requested {requested_list}.{sandbox_hint}"
        )
    return count


def sync_etrade_option_chain(
    symbol: str,
    expiry_date: str | None = None,
    max_contracts: int | None = None,
    etrade_credentials: dict[str, Any] | None = None,
) -> tuple[int, int]:
    """
    Fetch option chain from E*TRADE for symbol (and optional expiry), persist contracts and one bar per option.
    Returns (contracts_processed, total_bars_upserted).
    etrade_credentials: from user settings; else uses env vars.
    """
    kwargs = _etrade_kwargs(etrade_credentials)
    if not kwargs and not get_etrade_consumer_key():
        raise ValueError("E*TRADE credentials not set. Configure in Settings or environment.")
    resp = get_option_chain(symbol, expiry_date=expiry_date, resp_format="json", **kwargs)
    contracts_processed = 0
    total_bars = 0
    dt = _now_normalized()
    with session_scope() as session:
        contract_repo = OptionsContractRepository(session)
        bar_repo = OptionsBarRepository(session)
        # OptionChainResponse structure: OptionChainResponse > OptionPair[] > Call | Put > Option[]
        chain = resp.get("OptionChainResponse", {}).get("OptionPair") or resp.get("OptionPair")
        if not chain:
            return 0, 0
        pairs = chain if isinstance(chain, list) else [chain]
        for pair in pairs:
            for key in ("Call", "Put"):
                opts = pair.get(key) or pair.get(key.lower())
                if not opts:
                    continue
                option_type = "call" if key == "Call" else "put"
                opts_list = opts if isinstance(opts, list) else [opts]
                for opt in opts_list:
                    if max_contracts is not None and contracts_processed >= max_contracts:
                        break
                    sym = opt.get("symbol") or opt.get("Symbol") or opt.get("optionSymbol")
                    strike_raw = opt.get("strikePrice") or opt.get("StrikePrice")
                    exp_raw = opt.get("expiryDate") or opt.get("ExpiryDate") or expiry_date
                    if not sym or strike_raw is None:
                        continue
                    try:
                        strike = _float(strike_raw, 0.0)
                        if strike <= 0:
                            continue
                    except Exception:
                        continue
                    if exp_raw:
                        try:
                            if isinstance(exp_raw, str):
                                exp_dt = datetime.strptime(exp_raw[:10], "%Y-%m-%d")
                            else:
                                exp_dt = exp_raw
                        except Exception:
                            continue
                    else:
                        continue
                    contract = contract_repo.get_or_create(
                        underlying_symbol=symbol,
                        expiration=exp_dt,
                        strike=strike,
                        option_type=option_type,
                        contract_symbol=str(sym),
                    )
                    session.flush()
                    contracts_processed += 1
                    last = _float(opt.get("lastPrice") or opt.get("LastPrice") or opt.get("lastTrade"), 0.0)
                    bid = _float(opt.get("bid") or opt.get("Bid"), 0.0)
                    ask = _float(opt.get("ask") or opt.get("Ask"), 0.0)
                    vol = _int(opt.get("volume") or opt.get("Volume"), 0)
                    if last <= 0 and (bid <= 0 or ask <= 0):
                        mid = (bid + ask) / 2 if (bid and ask) else (bid or ask)
                        last = mid
                    o = last
                    bar_repo.upsert_bar(contract.id, dt, o, o, o, o, vol, open_interest=None)
                    total_bars += 1
    return contracts_processed, total_bars


def sync_etrade_option_expirations(
    symbol: str,
    etrade_credentials: dict[str, Any] | None = None,
) -> list[str]:
    """Fetch option expiration dates for symbol from E*TRADE. Returns list of YYYY-MM-DD strings."""
    kwargs = _etrade_kwargs(etrade_credentials)
    if not kwargs and not get_etrade_consumer_key():
        raise ValueError("E*TRADE credentials not set. Configure in Settings or environment.")
    resp = get_option_expire_dates(symbol, resp_format="json", **kwargs)
    # OptionExpireDateResponse > ExpirationDate array
    data = resp.get("OptionExpireDateResponse", {}).get("ExpirationDate") or resp.get("ExpirationDate")
    if not data:
        return []
    dates = data if isinstance(data, list) else [data]
    out = []
    for d in dates:
        if isinstance(d, dict):
            # May be {"year": 2024, "month": 12, "day": 20} or {"date": "2024-12-20"}
            if "date" in d:
                out.append(str(d["date"])[:10])
            elif "year" in d and "month" in d and "day" in d:
                out.append(f"{d['year']:04d}-{d['month']:02d}-{d['day']:02d}")
        elif isinstance(d, str):
            out.append(d[:10])
    return sorted(set(out))
