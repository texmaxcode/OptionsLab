"""Repository helpers to query options and underlying data for backtests."""

from datetime import datetime
from typing import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from models.sql_models import (
    UnderlyingBarModel,
    OptionsContractModel,
    OptionsBarModel,
)


def _normalize_datetime(dt: datetime) -> datetime:
    """Normalize datetime to midnight (date only) for bar key consistency."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


class UnderlyingBarRepository:
    """Query underlying OHLCV bars by symbol and date range."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_bar(self, symbol: str, dt: datetime, o: float, h: float, low: float, c: float, v: int) -> UnderlyingBarModel:
        """Insert or replace one underlying bar (idempotent by symbol+datetime)."""
        dt_norm = _normalize_datetime(dt)
        stmt = select(UnderlyingBarModel).where(
            UnderlyingBarModel.symbol == symbol,
            UnderlyingBarModel.datetime == dt_norm,
        )
        existing = self.session.execute(stmt).scalars().one_or_none()
        if existing:
            existing.open, existing.high, existing.low, existing.close, existing.volume = o, h, low, c, v
            return existing
        bar = UnderlyingBarModel(symbol=symbol, datetime=dt_norm, open=o, high=h, low=low, close=c, volume=v)
        self.session.add(bar)
        self.session.flush()
        return bar

    def get_bars(
        self,
        symbol: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Sequence[UnderlyingBarModel]:
        """Return underlying bars for symbol in [from_date, to_date], ordered by datetime."""
        q = select(UnderlyingBarModel).where(UnderlyingBarModel.symbol == symbol)
        if from_date is not None:
            q = q.where(UnderlyingBarModel.datetime >= from_date)
        if to_date is not None:
            q = q.where(UnderlyingBarModel.datetime <= to_date)
        q = q.order_by(UnderlyingBarModel.datetime)
        if limit is not None:
            q = q.limit(limit)
        if offset is not None:
            q = q.offset(offset)
        return list(self.session.execute(q).scalars().all())

    def count_bars(
        self,
        symbol: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> int:
        """Count underlying bars for symbol in [from_date, to_date]."""
        q = select(func.count()).select_from(UnderlyingBarModel).where(
            UnderlyingBarModel.symbol == symbol
        )
        if from_date is not None:
            q = q.where(UnderlyingBarModel.datetime >= from_date)
        if to_date is not None:
            q = q.where(UnderlyingBarModel.datetime <= to_date)
        return self.session.execute(q).scalar() or 0

    def delete_bars_by_symbol(self, symbol: str) -> int:
        """Delete all underlying bars for the given symbol. Returns count deleted."""
        result = self.session.execute(delete(UnderlyingBarModel).where(UnderlyingBarModel.symbol == symbol))
        return result.rowcount or 0


class OptionsContractRepository:
    """Query and upsert options contracts."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(
        self,
        underlying_symbol: str,
        expiration: datetime,
        strike: float,
        option_type: str,
        contract_symbol: str,
    ) -> OptionsContractModel:
        """Get existing contract by contract_symbol or create one."""
        stmt = select(OptionsContractModel).where(OptionsContractModel.contract_symbol == contract_symbol)
        existing = self.session.execute(stmt).scalars().one_or_none()
        if existing:
            return existing
        contract = OptionsContractModel(
            underlying_symbol=underlying_symbol,
            expiration=expiration,
            strike=strike,
            option_type=option_type,
            contract_symbol=contract_symbol,
        )
        self.session.add(contract)
        return contract

    def get_by_contract_symbol(self, contract_symbol: str) -> OptionsContractModel | None:
        stmt = select(OptionsContractModel).where(OptionsContractModel.contract_symbol == contract_symbol)
        return self.session.execute(stmt).scalars().one_or_none()

    def list_contracts(
        self,
        underlying_symbol: str | None = None,
        from_expiration: datetime | None = None,
        to_expiration: datetime | None = None,
        option_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Sequence[OptionsContractModel]:
        """List contracts with optional filters and pagination."""
        q = select(OptionsContractModel)
        if underlying_symbol:
            q = q.where(OptionsContractModel.underlying_symbol == underlying_symbol)
        if from_expiration:
            q = q.where(OptionsContractModel.expiration >= from_expiration)
        if to_expiration:
            q = q.where(OptionsContractModel.expiration <= to_expiration)
        if option_type:
            q = q.where(OptionsContractModel.option_type == option_type)
        q = q.order_by(OptionsContractModel.expiration, OptionsContractModel.strike)
        if limit is not None:
            q = q.limit(limit)
        if offset is not None:
            q = q.offset(offset)
        return list(self.session.execute(q).scalars().all())

    def count_contracts(
        self,
        underlying_symbol: str | None = None,
        from_expiration: datetime | None = None,
        to_expiration: datetime | None = None,
        option_type: str | None = None,
    ) -> int:
        """Count contracts matching the same filters as list_contracts."""
        q = select(func.count()).select_from(OptionsContractModel)
        if underlying_symbol:
            q = q.where(OptionsContractModel.underlying_symbol == underlying_symbol)
        if from_expiration:
            q = q.where(OptionsContractModel.expiration >= from_expiration)
        if to_expiration:
            q = q.where(OptionsContractModel.expiration <= to_expiration)
        if option_type:
            q = q.where(OptionsContractModel.option_type == option_type)
        return self.session.execute(q).scalar() or 0

    def delete_contracts_by_underlying(self, underlying_symbol: str) -> int:
        """Delete all options contracts (and their bars via cascade) for the underlying. Returns count deleted."""
        result = self.session.execute(
            delete(OptionsContractModel).where(OptionsContractModel.underlying_symbol == underlying_symbol)
        )
        return result.rowcount or 0


class OptionsBarRepository:
    """Query options bars for backtest feeds."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_bar(
        self,
        contract_id: int,
        dt: datetime,
        o: float,
        h: float,
        low: float,
        c: float,
        volume: int,
        open_interest: int | None = None,
        implied_volatility: float | None = None,
        delta: float | None = None,
        gamma: float | None = None,
        theta: float | None = None,
        vega: float | None = None,
    ) -> OptionsBarModel:
        """Insert or replace one options bar (idempotent by contract_id + datetime)."""
        dt_norm = _normalize_datetime(dt)
        target_date = dt_norm.date()
        # Query the exact contract+day instead of loading all bars for the contract.
        existing = self.session.execute(
            select(OptionsBarModel).where(
                OptionsBarModel.contract_id == contract_id,
                func.date(OptionsBarModel.datetime) == target_date.isoformat(),
            )
        ).scalars().one_or_none()
        if existing is None:
            existing = self.session.execute(
                select(OptionsBarModel).where(
                    OptionsBarModel.contract_id == contract_id,
                    OptionsBarModel.datetime == dt_norm,
                )
            ).scalars().one_or_none()
        if existing:
            existing.open, existing.high, existing.low, existing.close = o, h, low, c
            existing.volume = volume
            existing.open_interest = open_interest
            existing.implied_volatility = implied_volatility
            existing.delta, existing.gamma, existing.theta, existing.vega = delta, gamma, theta, vega
            return existing
        bar = OptionsBarModel(
            contract_id=contract_id,
            datetime=dt_norm,
            open=o,
            high=h,
            low=low,
            close=c,
            volume=volume,
            open_interest=open_interest,
            implied_volatility=implied_volatility,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
        )
        self.session.add(bar)
        self.session.flush()
        return bar

    def get_bars_for_contract(
        self,
        contract_id: int,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> Sequence[OptionsBarModel]:
        """Return options bars for one contract, ordered by datetime."""
        q = (
            select(OptionsBarModel)
            .where(OptionsBarModel.contract_id == contract_id)
            .order_by(OptionsBarModel.datetime)
        )
        if from_date is not None:
            q = q.where(OptionsBarModel.datetime >= from_date)
        if to_date is not None:
            q = q.where(OptionsBarModel.datetime <= to_date)
        return list(self.session.execute(q).scalars().all())

    def get_bars_for_contract_with_contract(
        self,
        contract_id: int,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> Sequence[OptionsBarModel]:
        """Same as get_bars_for_contract but eager-load contract for metadata."""
        q = (
            select(OptionsBarModel)
            .options(joinedload(OptionsBarModel.contract))
            .where(OptionsBarModel.contract_id == contract_id)
            .order_by(OptionsBarModel.datetime)
        )
        if from_date is not None:
            q = q.where(OptionsBarModel.datetime >= from_date)
        if to_date is not None:
            q = q.where(OptionsBarModel.datetime <= to_date)
        return list(self.session.execute(q).unique().scalars().all())

    def get_daily_iv_series(
        self,
        underlying_symbol: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[dict]:
        """
        Return daily average implied volatility for all contracts of an underlying.

        Groups by calendar date and averages IV across all active contracts.
        Rows with NULL implied_volatility are excluded. Results are sorted
        oldest-first and ready for volatility rank/percentile computation.

        Returns:
            List of {"date": str, "iv": float} dicts, sorted by date ascending.
        """
        stmt = (
            select(
                func.date(OptionsBarModel.datetime).label("date"),
                func.avg(OptionsBarModel.implied_volatility).label("avg_iv"),
            )
            .join(OptionsContractModel, OptionsBarModel.contract_id == OptionsContractModel.id)
            .where(OptionsContractModel.underlying_symbol == underlying_symbol)
            .where(OptionsBarModel.implied_volatility.isnot(None))
        )
        if from_date is not None:
            stmt = stmt.where(OptionsBarModel.datetime >= from_date)
        if to_date is not None:
            stmt = stmt.where(OptionsBarModel.datetime <= to_date)
        stmt = stmt.group_by(func.date(OptionsBarModel.datetime)).order_by(
            func.date(OptionsBarModel.datetime)
        )
        rows = self.session.execute(stmt).all()
        return [{"date": str(r.date), "iv": float(r.avg_iv)} for r in rows]
