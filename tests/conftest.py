"""Shared pytest fixtures and config."""

import os
import tempfile
import warnings

# Use in-memory DB for all tests before any storage/api imports
os.environ.setdefault("TRADING_DATABASE_URL", "sqlite:///:memory:")

import pytest

# Suppress statsmodels frequency inference warning if it appears (e.g. when index has no freq)
warnings.filterwarnings(
    "ignore",
    message="No frequency information was provided.*inferred frequency",
)


@pytest.fixture
def fresh_storage():
    """Reset storage module and create tables (for sync tests using in-memory DB)."""
    os.environ["TRADING_DATABASE_URL"] = "sqlite:///:memory:"
    import storage.session as mod
    mod._engine = None
    mod._session_factory = None
    from storage.session import create_all_tables
    create_all_tables()


@pytest.fixture
def fresh_storage_file():
    """Fresh DB in a temp file so all threads (e.g. FastAPI worker) share the same DB."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        url = f"sqlite:///{path}"
        os.environ["TRADING_DATABASE_URL"] = url
        import storage.session as mod
        mod._engine = None
        mod._session_factory = None
        from storage.session import create_all_tables
        create_all_tables()
        yield url
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.fixture
def etrade_env(monkeypatch):
    """Provide a consistent E*TRADE credential environment for tests."""
    monkeypatch.setenv("ETrade_CONSUMER_KEY", "ck")
    monkeypatch.setenv("ETrade_CONSUMER_SECRET", "cs")
    monkeypatch.setenv("ETrade_ACCESS_TOKEN", "at")
    monkeypatch.setenv("ETrade_ACCESS_SECRET", "ats")
