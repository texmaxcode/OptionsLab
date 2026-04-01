"""Unit tests for Pydantic schemas."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from models.pydantic_models import (
    UnderlyingBarIn,
    OptionsContractIn,
    OptionsBarIn,
    OptionsBarWithGreeksIn,
)


def test_underlying_bar_in_valid() -> None:
    bar = UnderlyingBarIn(
        symbol="AAPL",
        datetime=datetime(2024, 1, 15, 16, 0, 0),
        open=180.0,
        high=182.0,
        low=179.0,
        close=181.0,
        volume=1_000_000,
    )
    assert bar.symbol == "AAPL"
    assert bar.close == 181.0
    assert bar.volume == 1_000_000


def test_underlying_bar_in_negative_price_invalid() -> None:
    with pytest.raises(ValidationError):
        UnderlyingBarIn(
            symbol="AAPL",
            datetime=datetime(2024, 1, 15),
            open=-1.0,
            high=182.0,
            low=179.0,
            close=181.0,
            volume=1000,
        )


def test_options_contract_in_valid() -> None:
    c = OptionsContractIn(
        underlying_symbol="AAPL",
        expiration=datetime(2024, 12, 20),
        strike=150.0,
        option_type="call",
        contract_symbol="O:AAPL241220C00150000",
    )
    assert c.option_type == "call"
    assert c.strike == 150.0


def test_options_contract_in_put() -> None:
    c = OptionsContractIn(
        underlying_symbol="AAPL",
        expiration=datetime(2024, 12, 20),
        strike=150.0,
        option_type="put",
        contract_symbol="O:AAPL241220P00150000",
    )
    assert c.option_type == "put"


def test_options_contract_in_invalid_type() -> None:
    with pytest.raises(ValidationError):
        OptionsContractIn(
            underlying_symbol="AAPL",
            expiration=datetime(2024, 12, 20),
            strike=150.0,
            option_type="invalid",
            contract_symbol="O:AAPL241220C00150000",
        )


def test_options_bar_in_valid() -> None:
    b = OptionsBarIn(
        contract_symbol="O:AAPL241220C00150000",
        datetime=datetime(2024, 1, 15, 16, 0, 0),
        open=5.0,
        high=5.5,
        low=4.8,
        close=5.2,
        volume=100,
        open_interest=500,
    )
    assert b.close == 5.2
    assert b.open_interest == 500


def test_options_bar_with_greeks() -> None:
    b = OptionsBarWithGreeksIn(
        contract_symbol="O:AAPL241220C00150000",
        datetime=datetime(2024, 1, 15),
        open=5.0,
        high=5.5,
        low=4.8,
        close=5.2,
        volume=100,
        implied_volatility=0.25,
        delta=0.5,
    )
    assert b.implied_volatility == 0.25
    assert b.delta == 0.5
