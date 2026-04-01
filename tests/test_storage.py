"""Unit tests for storage layer (repositories + session) with in-memory SQLite."""

import os
from datetime import datetime

import pytest

os.environ["TRADING_DATABASE_URL"] = "sqlite:///:memory:"

from models.sql_models import Base
from storage.session import get_engine, get_session_factory
from storage.repositories import (
    UnderlyingBarRepository,
    OptionsContractRepository,
    OptionsBarRepository,
)


@pytest.fixture
def engine():
    """Per-test engine so each test gets a clean in-memory DB."""
    import storage.session as mod
    mod._engine = None
    mod._session_factory = None
    eng = get_engine()
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def session(engine):
    factory = get_session_factory()
    s = factory()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_underlying_bar_upsert_and_get(session) -> None:
    repo = UnderlyingBarRepository(session)
    dt = datetime(2024, 1, 15, 16, 0, 0)
    repo.upsert_bar("AAPL", dt, 180.0, 182.0, 179.0, 181.0, 1_000_000)
    session.commit()
    bars = repo.get_bars("AAPL", from_date=datetime(2024, 1, 1), to_date=datetime(2024, 1, 31))
    assert len(bars) == 1
    assert bars[0].symbol == "AAPL"
    assert bars[0].close == 181.0


def test_underlying_bar_upsert_idempotent(session) -> None:
    repo = UnderlyingBarRepository(session)
    dt = datetime(2024, 1, 15, 0, 0, 0, 0)
    repo.upsert_bar("AAPL", dt, 180.0, 182.0, 179.0, 181.0, 1000)
    repo.upsert_bar("AAPL", dt, 180.5, 182.5, 179.5, 181.5, 1100)
    session.commit()
    bars = repo.get_bars("AAPL")
    assert len(bars) == 1
    assert bars[0].close == 181.5
    assert bars[0].volume == 1100


def test_options_contract_get_or_create(session) -> None:
    repo = OptionsContractRepository(session)
    exp = datetime(2024, 12, 20)
    c1 = repo.get_or_create("AAPL", exp, 150.0, "call", "O:AAPL241220C00150000")
    session.flush()
    assert c1.id is not None
    c2 = repo.get_or_create("AAPL", exp, 150.0, "call", "O:AAPL241220C00150000")
    assert c1.id == c2.id


def test_options_bar_upsert_and_get(session) -> None:
    contract_repo = OptionsContractRepository(session)
    bar_repo = OptionsBarRepository(session)
    exp = datetime(2024, 12, 20)
    contract = contract_repo.get_or_create("AAPL", exp, 150.0, "call", "O:AAPL241220C00150000")
    session.flush()
    dt = datetime(2024, 1, 15)
    bar_repo.upsert_bar(contract.id, dt, 5.0, 5.5, 4.8, 5.2, 100, open_interest=500)
    session.commit()
    bars = bar_repo.get_bars_for_contract(contract.id)
    assert len(bars) == 1
    assert bars[0].close == 5.2
    assert bars[0].open_interest == 500


def test_get_by_contract_symbol(session) -> None:
    repo = OptionsContractRepository(session)
    exp = datetime(2024, 12, 20)
    repo.get_or_create("AAPL", exp, 150.0, "call", "O:AAPL241220C00150000")
    session.flush()
    c = repo.get_by_contract_symbol("O:AAPL241220C00150000")
    assert c is not None
    assert c.strike == 150.0
    assert repo.get_by_contract_symbol("NONEXISTENT") is None


def test_list_contracts(session) -> None:
    repo = OptionsContractRepository(session)
    exp1 = datetime(2024, 12, 20)
    exp2 = datetime(2025, 1, 17)
    repo.get_or_create("AAPL", exp1, 150.0, "call", "O:AAPL241220C00150000")
    repo.get_or_create("AAPL", exp1, 155.0, "put", "O:AAPL241220P00155000")
    repo.get_or_create("MSFT", exp2, 400.0, "call", "O:MSFT250117C00400000")
    session.flush()
    assert len(repo.list_contracts()) == 3
    assert len(repo.list_contracts(underlying_symbol="AAPL")) == 2
    assert len(repo.list_contracts(option_type="call")) == 2
    filtered = repo.list_contracts(
        underlying_symbol="AAPL",
        from_expiration=datetime(2024, 12, 1),
        to_expiration=datetime(2024, 12, 31),
    )
    assert len(filtered) == 2


def test_get_bars_for_contract_with_contract(session) -> None:
    contract_repo = OptionsContractRepository(session)
    bar_repo = OptionsBarRepository(session)
    exp = datetime(2024, 12, 20)
    c = contract_repo.get_or_create("AAPL", exp, 150.0, "call", "O:AAPL241220C00150000")
    session.flush()
    bar_repo.upsert_bar(c.id, datetime(2024, 1, 15), 5.0, 5.5, 4.8, 5.2, 100)
    session.commit()
    bars = bar_repo.get_bars_for_contract_with_contract(c.id)
    assert len(bars) == 1
    assert bars[0].contract is not None
    assert bars[0].contract.contract_symbol == "O:AAPL241220C00150000"


def test_get_bars_for_contract_with_contract_date_filter(session) -> None:
    contract_repo = OptionsContractRepository(session)
    bar_repo = OptionsBarRepository(session)
    exp = datetime(2024, 12, 20)
    c = contract_repo.get_or_create("AAPL", exp, 150.0, "call", "O:AAPL241220C00150000")
    session.flush()
    bar_repo.upsert_bar(c.id, datetime(2024, 1, 15), 5.0, 5.5, 4.8, 5.2, 100)
    bar_repo.upsert_bar(c.id, datetime(2024, 1, 16), 5.2, 5.6, 5.0, 5.4, 110)
    session.commit()
    bars = bar_repo.get_bars_for_contract_with_contract(
        c.id, from_date=datetime(2024, 1, 16), to_date=datetime(2024, 1, 16)
    )
    assert len(bars) == 1
    assert bars[0].close == 5.4


def test_options_bar_upsert_idempotent(session) -> None:
    contract_repo = OptionsContractRepository(session)
    bar_repo = OptionsBarRepository(session)
    exp = datetime(2024, 12, 20)
    c = contract_repo.get_or_create("AAPL", exp, 150.0, "call", "O:AAPL241220C00150000")
    session.flush()
    bar_repo.upsert_bar(c.id, datetime(2024, 1, 15), 5.0, 5.5, 4.8, 5.2, 100, implied_volatility=0.25)
    bar_repo.upsert_bar(c.id, datetime(2024, 1, 15), 5.1, 5.6, 4.9, 5.3, 120, implied_volatility=0.26)
    session.commit()
    bars = bar_repo.get_bars_for_contract(c.id)
    assert len(bars) == 1
    assert bars[0].close == 5.3
    assert bars[0].volume == 120
    assert bars[0].implied_volatility == 0.26
