"""Tests for storage/session."""

import os

import pytest

os.environ["TRADING_DATABASE_URL"] = "sqlite:///:memory:"

from models.sql_models import Base
from storage.session import get_engine, get_session_factory, session_scope, create_all_tables


def test_get_engine():
    import storage.session as mod
    mod._engine = None
    mod._session_factory = None
    engine = get_engine()
    assert engine is not None
    assert str(engine.url).startswith("sqlite")


def test_get_session_factory():
    import storage.session as mod
    mod._session_factory = None
    factory = get_session_factory()
    assert factory is not None
    session = factory()
    assert session is not None
    session.close()


def test_session_scope_commit():
    import storage.session as mod
    mod._engine = None
    mod._session_factory = None
    Base.metadata.create_all(bind=get_engine())
    with session_scope() as session:
        from models.sql_models import UnderlyingBarModel
        from datetime import datetime
        session.add(UnderlyingBarModel(symbol="T", datetime=datetime(2024,1,1), open=1, high=1, low=1, close=1, volume=0))
    with session_scope() as session:
        from sqlalchemy import select
        r = list(session.execute(select(UnderlyingBarModel).where(UnderlyingBarModel.symbol == "T")).scalars().all())
        assert len(r) == 1


def test_session_scope_rollback_on_error():
    import storage.session as mod
    mod._engine = None
    mod._session_factory = None
    Base.metadata.create_all(bind=get_engine())
    with pytest.raises(RuntimeError):
        with session_scope() as session:
            from models.sql_models import UnderlyingBarModel
            from datetime import datetime
            session.add(UnderlyingBarModel(symbol="T2", datetime=datetime(2024,1,1), open=1, high=1, low=1, close=1, volume=0))
            raise RuntimeError("abort")
    with session_scope() as session:
        from sqlalchemy import select
        from models.sql_models import UnderlyingBarModel
        r = list(session.execute(select(UnderlyingBarModel).where(UnderlyingBarModel.symbol == "T2")).scalars().all())
        assert len(r) == 0


def test_create_all_tables():
    import storage.session as mod
    mod._engine = None
    mod._session_factory = None
    create_all_tables()
    engine = get_engine()
    from sqlalchemy import inspect
    insp = inspect(engine)
    assert "underlying_bars" in insp.get_table_names()
