"""GET /contracts, GET /symbols - list options contracts and underlying symbols."""

from fastapi import APIRouter, Depends, Query, status

from sqlalchemy import select

from api import auth_utils
from api.schemas import ContractInfo, ContractsPage, UnderlyingBarInfo, UnderlyingBarsPage
from models.sql_models import UnderlyingBarModel, OptionsContractModel, UserModel
from storage import session_scope, OptionsContractRepository, UnderlyingBarRepository

router = APIRouter(tags=["contracts", "symbols"])


@router.delete("/symbols/{symbol}", status_code=status.HTTP_200_OK)
def delete_symbol_data(
    symbol: str,
    _: UserModel = Depends(auth_utils.get_current_user),
):
    """Delete all data for the symbol: underlying bars and options contracts (with their bars)."""
    with session_scope() as session:
        bar_repo = UnderlyingBarRepository(session)
        contract_repo = OptionsContractRepository(session)
        bars_deleted = bar_repo.delete_bars_by_symbol(symbol)
        contracts_deleted = contract_repo.delete_contracts_by_underlying(symbol)
    return {
        "symbol": symbol,
        "underlying_bars_deleted": bars_deleted,
        "options_contracts_deleted": contracts_deleted,
    }

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500


@router.get("/symbols", response_model=list[str])
def list_symbols():
    """Return distinct underlying symbols present in DB (from underlying bars and options contracts)."""
    with session_scope() as session:
        from_bars = session.execute(select(UnderlyingBarModel.symbol).distinct()).scalars().all()
        from_contracts = session.execute(select(OptionsContractModel.underlying_symbol).distinct()).scalars().all()
        combined = set(from_bars) | set(from_contracts)
        return sorted(combined)


@router.get("/contracts", response_model=ContractsPage)
def list_contracts(
    underlying: str = Query(..., description="Underlying symbol (e.g. AAPL)"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Number of records per page",
    ),
):
    """Return options contracts for the given underlying symbol, with pagination."""
    with session_scope() as session:
        repo = OptionsContractRepository(session)
        total = repo.count_contracts(underlying_symbol=underlying)
        offset = (page - 1) * page_size
        contracts = repo.list_contracts(
            underlying_symbol=underlying,
            limit=page_size,
            offset=offset,
        )
        items = [
            ContractInfo(
                id=c.id,
                underlying_symbol=c.underlying_symbol,
                expiration=c.expiration.strftime("%Y-%m-%d") if c.expiration else "",
                strike=c.strike,
                option_type=c.option_type,
                contract_symbol=c.contract_symbol,
            )
            for c in contracts
        ]
        return ContractsPage(items=items, total=total)


@router.get("/bars", response_model=UnderlyingBarsPage)
def list_underlying_bars(
    symbol: str = Query(..., description="Underlying symbol (e.g. AAPL)"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Number of records per page",
    ),
):
    """Return underlying OHLCV bars for the given symbol, with pagination."""
    with session_scope() as session:
        repo = UnderlyingBarRepository(session)
        total = repo.count_bars(symbol=symbol)
        offset = (page - 1) * page_size
        bars = repo.get_bars(symbol=symbol, limit=page_size, offset=offset)
        items = [
            UnderlyingBarInfo(
                date=b.datetime.strftime("%Y-%m-%d") if b.datetime else "",
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
            )
            for b in bars
        ]
        return UnderlyingBarsPage(items=items, total=total)
