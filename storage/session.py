"""SQLAlchemy engine and session management."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_database_url
from models.sql_models import Base


_engine = None
_session_factory = None


def get_engine():
    """Create or return shared engine. Uses TRADING_DATABASE_URL or default SQLite."""
    global _engine
    if _engine is None:
        url = get_database_url()
        _engine = create_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return session factory bound to engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autocommit=False, autoflush=False, expire_on_commit=False
        )
    return _session_factory


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for a single session; commits on success, rolls back on error."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_tables() -> None:
    """Create all tables (for init or one-off script). No Alembic."""
    Base.metadata.create_all(bind=get_engine())
