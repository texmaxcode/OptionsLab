"""SQLAlchemy ORM models for persistence."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow_naive() -> datetime:
    """UTC "now" as naive datetime (stored in DB without timezone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    type_annotation_map = {
        datetime: DateTime(timezone=False),
    }


class UnderlyingBarModel(Base):
    """Underlying OHLCV bars (one row per symbol + datetime)."""

    __tablename__ = "underlying_bars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_underlying_bars_symbol_datetime", "symbol", "datetime", unique=True),
    )


class OptionsContractModel(Base):
    """Options contract metadata. One row per contract."""

    __tablename__ = "options_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    underlying_symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    expiration: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    strike: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    option_type: Mapped[str] = mapped_column(String(8), nullable=False)  # 'call' | 'put'
    contract_symbol: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    bars: Mapped[list["OptionsBarModel"]] = relationship(
        "OptionsBarModel", back_populates="contract", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "ix_options_contracts_underlying_exp_strike_type",
            "underlying_symbol",
            "expiration",
            "strike",
            "option_type",
        ),
    )


class OptionsBarModel(Base):
    """Options OHLCV bars. One row per (contract_id, datetime). Optional IV/Greeks."""

    __tablename__ = "options_bars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("options_contracts.id", ondelete="CASCADE"), nullable=False
    )
    datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    open_interest: Mapped[int | None] = mapped_column(Integer, nullable=True)
    implied_volatility: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    gamma: Mapped[float | None] = mapped_column(Float, nullable=True)
    theta: Mapped[float | None] = mapped_column(Float, nullable=True)
    vega: Mapped[float | None] = mapped_column(Float, nullable=True)

    contract: Mapped["OptionsContractModel"] = relationship(
        "OptionsContractModel", back_populates="bars"
    )

    __table_args__ = (
        Index("ix_options_bars_contract_datetime", "contract_id", "datetime", unique=True),
    )


class UserModel(Base):
    """Application user for dashboard/auth."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow_naive, index=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    settings_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON-encoded user settings

    backtests: Mapped[list["BacktestModel"]] = relationship(
        "BacktestModel", back_populates="user", cascade="all, delete-orphan"
    )


class BacktestModel(Base):
    """Saved backtest run for a user."""

    __tablename__ = "backtests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow_naive, index=True
    )

    # Parameters
    strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    underlying: Mapped[str] = mapped_column(String(32), nullable=False)
    from_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    to_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cash: Mapped[float] = mapped_column(Float, nullable=False, default=100_000.0)
    contract_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_symbol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_contract: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Result
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="completed", index=True
    )  # completed | failed
    start_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="backtests")

    __table_args__ = (
        Index("ix_backtests_user_created_at", "user_id", "created_at"),
    )


class BacktestEquityPointModel(Base):
    """Per-backtest equity curve points (date, value)."""

    __tablename__ = "backtest_equity_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_backtest_equity_points_bt_date", "backtest_id", "date"),
    )


class BacktestReturnPointModel(Base):
    """Per-backtest periodic returns (used for period returns chart and stats)."""

    __tablename__ = "backtest_returns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    period_return: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_backtest_returns_bt_date", "backtest_id", "date"),
    )


class BacktestPricePointModel(Base):
    """Per-backtest price series (date, close) for the price/indicators/trades chart."""

    __tablename__ = "backtest_price_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_backtest_price_points_bt_date", "backtest_id", "date"),
    )


class BacktestTradeModel(Base):
    """Trades generated by a backtest."""

    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    exit_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_days: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_backtest_trades_bt_entry", "backtest_id", "entry_date"),
    )


class BacktestIndicatorPointModel(Base):
    """Indicator series per backtest (stored as JSON blob per date)."""

    __tablename__ = "backtest_indicator_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    indicators_json: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_backtest_indicator_bt_date", "backtest_id", "date"),
    )


class EconomicSeriesModel(Base):
    """Metadata for a macro / economic time series (e.g. FRED GDP)."""

    __tablename__ = "economic_series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    series_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(256), nullable=True)

    points: Mapped[list["EconomicSeriesPointModel"]] = relationship(
        "EconomicSeriesPointModel", back_populates="series", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_economic_series_source_series", "source", "series_id", unique=True),
    )


class EconomicSeriesPointModel(Base):
    """Stored macro / economic data points (date, value) for a series."""

    __tablename__ = "economic_series_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id_fk: Mapped[int] = mapped_column(
        Integer, ForeignKey("economic_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)

    series: Mapped["EconomicSeriesModel"] = relationship(
        "EconomicSeriesModel", back_populates="points"
    )

    __table_args__ = (
        Index("ix_economic_series_points_series_date", "series_id_fk", "date", unique=True),
    )
