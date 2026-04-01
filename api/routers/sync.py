"""POST /lab/sync - run data sync (Massive or E*TRADE) from the dashboard."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status

from api import auth_utils
from api.schemas import SyncRequest, SyncResponse, SyncResult
from api.user_settings_utils import extract_unmasked_settings, load_user_settings
from config import (
    get_massive_api_key,
    get_etrade_consumer_key,
    get_sync_default_symbol,
    get_sync_date_from,
    get_sync_date_to,
)
from data import (
    sync_underlying_bars,
    sync_options_chain_and_bars,
    sync_etrade_quotes,
    sync_etrade_option_chain,
)
from models.sql_models import UserModel
from storage import session_scope

router = APIRouter(prefix="/lab", tags=["lab", "sync"])


def _credentials_from_user(user) -> dict:
    """Extract API credentials from user settings. Excludes masked values."""
    data = load_user_settings(user)
    creds = extract_unmasked_settings(
        data,
        keys=(
            "massive_api_key",
            "etrade_consumer_key",
            "etrade_consumer_secret",
            "etrade_access_token",
            "etrade_access_secret",
            "etrade_sandbox",
        ),
    )
    if "etrade_sandbox" in creds and not isinstance(creds["etrade_sandbox"], bool):
        creds.pop("etrade_sandbox", None)
    return creds


def _run_massive_sync(req: SyncRequest, creds: dict) -> SyncResponse:
    """Run Massive sync (blocking). Uses creds from Settings or env."""
    api_key = creds.get("massive_api_key") or get_massive_api_key()
    if not api_key:
        return SyncResponse(
            success=False,
            total_underlying_bars=0,
            results=[],
            error="Massive API key not set. Configure in Settings or set MASSIVE_API_KEY in environment.",
        )
    symbols = [s.strip() for s in req.symbols.split(",") if s.strip()]
    if not symbols:
        symbols = [get_sync_default_symbol()]
    from_date = req.from_date or get_sync_date_from()
    to_date = req.to_date or get_sync_date_to()

    results: list[SyncResult] = []
    total_underlying_bars = 0

    try:
        for symbol in symbols:
            try:
                n = sync_underlying_bars(symbol, from_date, to_date, massive_api_key=api_key)
                total_underlying_bars += n
                opts_contracts = None
                opts_bars = None
                if not req.underlying_only:
                    try:
                        c, b = sync_options_chain_and_bars(
                            symbol,
                            from_date,
                            to_date,
                            max_contracts=req.max_contracts,
                            massive_api_key=api_key,
                        )
                        opts_contracts = c
                        opts_bars = b
                    except Exception as opt_e:
                        results.append(
                            SyncResult(
                                symbol=symbol,
                                underlying_bars=n,
                                error=str(opt_e),
                            )
                        )
                        continue
                results.append(
                    SyncResult(
                        symbol=symbol,
                        underlying_bars=n,
                        options_contracts=opts_contracts,
                        options_bars=opts_bars,
                    )
                )
            except Exception as e:
                results.append(
                    SyncResult(symbol=symbol, underlying_bars=0, error=str(e))
                )
        return SyncResponse(
            success=True,
            total_underlying_bars=total_underlying_bars,
            results=results,
        )
    except Exception as e:
        return SyncResponse(
            success=False,
            total_underlying_bars=total_underlying_bars,
            results=results,
            error=str(e),
        )


def _run_etrade_sync(req: SyncRequest, creds: dict) -> SyncResponse:
    """Run E*TRADE sync (blocking). Uses creds from Settings or env."""
    etrade_creds = {k: v for k, v in creds.items() if k.startswith("etrade_")} or None
    if not etrade_creds and not get_etrade_consumer_key():
        return SyncResponse(
            success=False,
            total_underlying_bars=0,
            results=[],
            error="E*TRADE credentials not set. Configure in Settings or set ETrade_* env vars.",
        )
    symbols = [s.strip() for s in req.symbols.split(",") if s.strip()]
    if not symbols:
        symbols = [get_sync_default_symbol()]

    try:
        total_underlying_bars = 0
        results: list[SyncResult] = []
        for sym in symbols:
            try:
                underlying_n = sync_etrade_quotes([sym], etrade_credentials=etrade_creds)
                total_underlying_bars += underlying_n
            except Exception as e:
                results.append(
                    SyncResult(symbol=sym, underlying_bars=0, error=str(e))
                )
                continue

            opts_contracts = None
            opts_bars = None
            if req.options:
                try:
                    c, b = sync_etrade_option_chain(
                        sym,
                        max_contracts=req.max_contracts,
                        etrade_credentials=etrade_creds,
                    )
                    opts_contracts = c
                    opts_bars = b
                except Exception as opt_e:
                    results.append(
                        SyncResult(
                            symbol=sym,
                            underlying_bars=underlying_n,
                            error=str(opt_e),
                        )
                    )
                    continue
            results.append(
                SyncResult(
                    symbol=sym,
                    underlying_bars=underlying_n,
                    options_contracts=opts_contracts,
                    options_bars=opts_bars,
                )
            )
        return SyncResponse(
            success=True,
            total_underlying_bars=total_underlying_bars,
            results=results,
        )
    except Exception as e:
        return SyncResponse(
            success=False,
            total_underlying_bars=0,
            results=[],
            error=str(e),
        )


@router.post("/sync", response_model=SyncResponse)
async def run_sync(
    req: SyncRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """
    Run data sync (Massive or E*TRADE). Symbols are comma-separated.
    Massive: requires from_date, to_date. Set underlying_only=True to skip options.
    E*TRADE: set options=True to also sync option chain.
    """
    if req.source not in ("massive", "etrade"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source must be 'massive' or 'etrade'",
        )
    if req.source == "massive" and (not req.from_date or not req.to_date):
        req.from_date = req.from_date or get_sync_date_from()
        req.to_date = req.to_date or get_sync_date_to()

    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _credentials_from_user(user) if user else {}

    fn = _run_massive_sync if req.source == "massive" else _run_etrade_sync
    return await asyncio.to_thread(fn, req, creds)
