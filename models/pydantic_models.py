"""Pydantic schemas for validation and API/CSV boundary."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UnderlyingBarIn(BaseModel):
    """One OHLCV bar for the underlying (e.g. equity)."""

    symbol: str = Field(..., min_length=1, max_length=32)
    datetime: datetime
    open: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    low: float = Field(..., ge=0)
    close: float = Field(..., ge=0)
    volume: int = Field(..., ge=0)


class OptionsContractIn(BaseModel):
    """Options contract metadata (underlying, expiration, strike, type, contract symbol)."""

    underlying_symbol: str = Field(..., min_length=1, max_length=32)
    expiration: datetime  # expiration date
    strike: float = Field(..., gt=0)
    option_type: Literal["call", "put"]
    contract_symbol: str = Field(..., min_length=1, max_length=64)  # e.g. OCC symbol


class OptionsBarIn(BaseModel):
    """One OHLCV bar for an option contract. Optional open_interest."""

    contract_symbol: str = Field(..., min_length=1, max_length=64)
    datetime: datetime
    open: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    low: float = Field(..., ge=0)
    close: float = Field(..., ge=0)
    volume: int = Field(..., ge=0)
    open_interest: int | None = Field(default=None, ge=0)


class OptionsBarWithGreeksIn(OptionsBarIn):
    """Options bar with optional Greeks and implied volatility."""

    implied_volatility: float | None = Field(default=None, ge=0)
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
