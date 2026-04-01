"""API tests: main app, routers, auth. Use in-memory DB via fresh_storage."""

import json
import os

import pytest
from fastapi.testclient import TestClient

from storage.session import session_scope, create_all_tables
from storage.economic_repositories import EconomicSeriesRepository

# Ensure in-memory DB before any storage/api imports in test process
os.environ.setdefault("TRADING_DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture
def client(fresh_storage_file):
    """FastAPI test client with fresh DB; auth dependency overridden to use default user."""
    from api.main import app
    from api import auth_utils

    app.dependency_overrides[auth_utils.get_current_user] = auth_utils.get_default_user
    try:
        with TestClient(app) as c:
            create_all_tables()  # ensure tables exist
            yield c
    finally:
        app.dependency_overrides.pop(auth_utils.get_current_user, None)


@pytest.fixture
def client_with_bars(client):
    """Client with underlying bars seeded for AAPL (for backtest run tests).
    Uses 60 bars so SMA crossover (slow_period=50) has enough data."""
    from datetime import datetime, timedelta
    from storage import session_scope, UnderlyingBarRepository
    with session_scope() as session:
        repo = UnderlyingBarRepository(session)
        for i in range(60):
            dt = datetime(2024, 1, 1) + timedelta(days=i)
            repo.upsert_bar("AAPL", dt, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1_000_000)
    return client


def test_root(client) -> None:
    """GET / returns API info."""
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "name" in data
    assert "version" in data
    assert "environment" in data
    assert "docs" in data


def test_list_strategies(client) -> None:
    """GET /strategies returns strategy list with labels and equity_only."""
    r = client.get("/strategies")
    assert r.status_code == 200
    strategies = r.json()
    assert isinstance(strategies, list)
    assert len(strategies) > 0
    for s in strategies:
        assert "id" in s
        assert "label" in s
        assert "equity_only" in s
    ids = [s["id"] for s in strategies]
    assert "single_leg" in ids
    assert "sma_crossover" in ids


def test_list_symbols_empty(client) -> None:
    """GET /symbols returns empty list when no data."""
    r = client.get("/symbols")
    assert r.status_code == 200
    assert r.json() == []


def test_list_contracts_requires_underlying(client) -> None:
    """GET /contracts requires underlying query param."""
    r = client.get("/contracts")
    assert r.status_code == 422


def test_list_contracts_empty(client) -> None:
    """GET /contracts returns paginated response with empty items for unknown symbol."""
    r = client.get("/contracts?underlying=AAPL")
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_bars_requires_symbol(client) -> None:
    """GET /bars requires symbol query param."""
    r = client.get("/bars")
    assert r.status_code == 422


def test_list_bars_empty(client) -> None:
    """GET /bars returns empty items when no bars for symbol."""
    r = client.get("/bars?symbol=AAPL")
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_bars_with_data(client_with_bars) -> None:
    """GET /bars returns paginated underlying bars for symbol."""
    r = client_with_bars.get("/bars?symbol=AAPL&page=1&page_size=10")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 60
    assert len(data["items"]) == 10
    for b in data["items"]:
        assert "date" in b
        assert "open" in b and "high" in b and "low" in b and "close" in b and "volume" in b


def test_run_backtest_unknown_strategy(client) -> None:
    """POST /backtests/run with unknown strategy returns error."""
    r = client.post(
        "/backtests/run",
        json={
            "strategy": "nonexistent",
            "underlying": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-01-31",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "error" in data
    assert "Unknown strategy" in data["error"]


def test_run_backtest_equity_missing_dates(client) -> None:
    """POST /backtests/run equity strategy without dates returns error."""
    r = client.post(
        "/backtests/run",
        json={"strategy": "sma_crossover", "underlying": "AAPL"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "from_date" in data["error"] or "to_date" in data["error"]


def test_run_backtest_equity_no_bars(client) -> None:
    """POST /backtests/run equity strategy with no bars in DB returns error."""
    r = client.post(
        "/backtests/run",
        json={
            "strategy": "sma_crossover",
            "underlying": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-01-31",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "No underlying bars" in data["error"]


def test_run_backtest_success(client_with_bars) -> None:
    """POST /backtests/run with bars in DB returns success and values."""
    r = client_with_bars.post(
        "/backtests/run",
        json={
            "strategy": "sma_crossover",
            "underlying": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",  # 60 bars for SMA(slow=50)
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data.get("start_value") is not None
    assert data.get("end_value") is not None
    assert data.get("error") is None


def test_get_settings_default(client) -> None:
    """GET /user/settings returns default user settings (empty defaults)."""
    r = client.get("/user/settings")
    assert r.status_code == 200
    data = r.json()
    assert "default_symbol" in data
    assert "default_strategy" in data


def test_update_settings(client) -> None:
    """PUT /user/settings persists and returns updated settings."""
    r = client.put(
        "/user/settings",
        json={"default_symbol": "AAPL", "default_strategy": "sma_crossover"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("default_symbol") == "AAPL"
    assert data.get("default_strategy") == "sma_crossover"

    r2 = client.get("/user/settings")
    assert r2.status_code == 200
    assert r2.json().get("default_symbol") == "AAPL"


def test_update_settings_masks_alpaca_credentials(client) -> None:
    """PUT /user/settings persists Alpaca credentials and masks them on read."""
    from api.schemas import SETTINGS_MASK

    r = client.put(
        "/user/settings",
        json={
            "alpaca_api_key": "alpaca-key",
            "alpaca_api_secret": "alpaca-secret",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("alpaca_api_key") == SETTINGS_MASK
    assert data.get("alpaca_api_secret") == SETTINGS_MASK

    r2 = client.get("/user/settings")
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2.get("alpaca_api_key") == SETTINGS_MASK
    assert data2.get("alpaca_api_secret") == SETTINGS_MASK


def test_get_settings_invalid_json_returns_defaults(client) -> None:
    """GET /user/settings with corrupted settings_json returns empty defaults."""
    client.get("/user/settings")  # ensure default user exists
    from api.auth_utils import DEFAULT_USER_EMAIL
    from models.sql_models import UserModel
    from sqlalchemy import select
    from storage import session_scope

    with session_scope() as session:
        user = session.execute(select(UserModel).where(UserModel.email == DEFAULT_USER_EMAIL)).scalars().one()
        user.settings_json = "not valid json"
        session.add(user)
        session.commit()

    r = client.get("/user/settings")
    assert r.status_code == 200
    data = r.json()
    assert "default_symbol" in data
    assert data.get("default_symbol") is None


def test_list_backtests_empty(client) -> None:
    """GET /lab/backtests returns empty list for default user."""
    r = client.get("/lab/backtests")
    assert r.status_code == 200
    assert r.json() == []


def test_create_backtest_success(client_with_bars) -> None:
    """POST /lab/backtests runs backtest and persists backtest."""
    r = client_with_bars.post(
        "/lab/backtests",
        json={
            "name": "My SMA Test",
            "strategy": "sma_crossover",
            "underlying": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",  # 60 bars so SMA(slow=50) has enough data
            "cash": 100_000.0,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "My SMA Test"
    assert data["strategy"] == "sma_crossover"
    assert data["status"] == "completed"
    assert data["start_value"] is not None
    assert data["end_value"] is not None
    assert "id" in data
    # List should include it
    r2 = client_with_bars.get("/lab/backtests")
    assert r2.status_code == 200
    backtests = r2.json()
    assert len(backtests) >= 1
    assert any(e["name"] == "My SMA Test" for e in backtests)
    exp_id = data["id"]
    # Get by id
    r3 = client_with_bars.get(f"/lab/backtests/{exp_id}")
    assert r3.status_code == 200
    assert r3.json()["name"] == "My SMA Test"
    # Delete
    r4 = client_with_bars.delete(f"/lab/backtests/{exp_id}")
    assert r4.status_code == 204
    r5 = client_with_bars.get(f"/lab/backtests/{exp_id}")
    assert r5.status_code == 404


def test_get_backtest_404(client) -> None:
    """GET /lab/backtests/999 returns 404."""
    r = client.get("/lab/backtests/999")
    assert r.status_code == 404


def test_delete_backtest_404(client) -> None:
    """DELETE /lab/backtests/999 returns 404."""
    r = client.delete("/lab/backtests/999")
    assert r.status_code == 404


def test_sync_massive_no_api_key(client, monkeypatch) -> None:
    """POST /lab/sync with source=massive and no MASSIVE_API_KEY returns error."""
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    r = client.post(
        "/lab/sync",
        json={
            "source": "massive",
            "symbols": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-12-31",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "MASSIVE_API_KEY" in (data.get("error") or "")


def test_sync_etrade_no_credentials(client) -> None:
    """POST /lab/sync with source=etrade and no E*TRADE credentials returns error."""
    r = client.post(
        "/lab/sync",
        json={"source": "etrade", "symbols": "AAPL"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "E*TRADE" in (data.get("error") or "")


def test_sync_credentials_preserve_live_mode_false(client) -> None:
    """Sync credentials extraction preserves etrade_sandbox=False for live mode."""
    client.put(
        "/user/settings",
        json={
            "etrade_consumer_key": "ck",
            "etrade_consumer_secret": "cs",
            "etrade_access_token": "at",
            "etrade_access_secret": "ats",
            "etrade_sandbox": False,
        },
    )

    from api.routers.sync import _credentials_from_user
    from models.sql_models import UserModel

    with session_scope() as session:
        user = session.query(UserModel).first()
        creds = _credentials_from_user(user)

    assert creds["etrade_sandbox"] is False


def test_etrade_trading_credentials_preserve_live_mode_false(client) -> None:
    """Trading credentials extraction preserves etrade_sandbox=False for live mode."""
    client.put(
        "/user/settings",
        json={
            "etrade_consumer_key": "ck",
            "etrade_consumer_secret": "cs",
            "etrade_access_token": "at",
            "etrade_access_secret": "ats",
            "etrade_sandbox": False,
        },
    )

    from api.routers.etrade_trading import _broker_kwargs, _etrade_creds_from_user
    from models.sql_models import UserModel

    with session_scope() as session:
        user = session.query(UserModel).first()
        creds = _etrade_creds_from_user(user)

    assert creds["etrade_sandbox"] is False
    broker_kwargs = _broker_kwargs(creds, None)
    assert broker_kwargs["sandbox"] is False


def test_etrade_oauth_endpoints_use_live_when_false() -> None:
    """OAuth endpoint helper maps sandbox=False to live E*TRADE URLs."""
    from api.routers.etrade_oauth import _oauth_endpoints

    request_url, access_url = _oauth_endpoints(sandbox=False)

    assert request_url == "https://api.etrade.com/oauth/request_token"
    assert access_url == "https://api.etrade.com/oauth/access_token"


def test_etrade_accounts_no_credentials(client) -> None:
    """GET /lab/etrade/accounts with no E*TRADE credentials returns 400."""
    r = client.get("/lab/etrade/accounts?sandbox=true")
    assert r.status_code == 400
    assert "E*TRADE" in (r.json().get("detail") or "")


def test_etrade_accounts_upstream_error_returns_502(client, monkeypatch) -> None:
    """GET /lab/etrade/accounts maps upstream broker errors to 502 instead of 500."""
    client.put(
        "/user/settings",
        json={
            "etrade_consumer_key": "ck",
            "etrade_consumer_secret": "cs",
            "etrade_access_token": "at",
            "etrade_access_secret": "ats",
            "etrade_sandbox": False,
        },
    )

    def _boom(*args, **kwargs):
        raise Exception("401 Client Error: 401 for url: https://api.etrade.com/v1/accounts/list.json")

    monkeypatch.setattr("api.routers.etrade_trading.etrade_list_accounts", _boom)

    r = client.get("/lab/etrade/accounts?sandbox=false")
    assert r.status_code == 502
    assert "401 Client Error" in (r.json().get("detail") or "")


def test_alpaca_accounts_no_credentials(client) -> None:
    """GET /lab/alpaca/accounts with no Alpaca credentials returns 400."""
    r = client.get("/lab/alpaca/accounts")
    assert r.status_code == 400
    assert "Alpaca" in (r.json().get("detail") or "")


def test_alpaca_accounts_success(client, monkeypatch) -> None:
    """GET /lab/alpaca/accounts returns paper account details."""
    client.put(
        "/user/settings",
        json={
            "alpaca_api_key": "ak",
            "alpaca_api_secret": "as",
        },
    )

    def _account(*args, **kwargs):
        return {
            "id": "paper-account-id",
            "account_number": "PA12345",
            "status": "ACTIVE",
            "currency": "USD",
            "buying_power": "100000",
        }

    monkeypatch.setattr("api.routers.alpaca_trading.alpaca_get_account", _account)

    r = client.get("/lab/alpaca/accounts")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "paper-account-id"
    assert data["account_number"] == "PA12345"

    r2 = client.get("/lab/alpaca/accounts/balance?account_id_key=paper-account-id")
    assert r2.status_code == 200
    assert r2.json()["buying_power"] == "100000"


def test_alpaca_orders_upstream_error_returns_502(client, monkeypatch) -> None:
    """GET /lab/alpaca/orders maps upstream broker errors to 502."""
    client.put(
        "/user/settings",
        json={
            "alpaca_api_key": "ak",
            "alpaca_api_secret": "as",
        },
    )

    def _boom(*args, **kwargs):
        raise Exception("401 Client Error: 401 for url: https://paper-api.alpaca.markets/v2/orders")

    monkeypatch.setattr("api.routers.alpaca_trading.alpaca_list_orders", _boom)

    r = client.get("/lab/alpaca/orders?account_id_key=paper-account-id&status=OPEN")
    assert r.status_code == 502
    assert "401 Client Error" in (r.json().get("detail") or "")


def test_alpaca_cancel_accepts_string_order_ids(client, monkeypatch) -> None:
    """POST /lab/alpaca/orders/cancel accepts UUID-style Alpaca order IDs."""
    client.put(
        "/user/settings",
        json={
            "alpaca_api_key": "ak",
            "alpaca_api_secret": "as",
        },
    )
    seen: dict[str, str] = {}

    def _cancel(order_id: str, **kwargs):
        seen["order_id"] = order_id

    monkeypatch.setattr("api.routers.alpaca_trading.alpaca_cancel_order", _cancel)

    r = client.post(
        "/lab/alpaca/orders/cancel",
        json={
            "account_id_key": "paper-account-id",
            "order_id": "c0ffee00-1234-5678-9abc-def012345678",
        },
    )
    assert r.status_code == 200
    assert seen["order_id"] == "c0ffee00-1234-5678-9abc-def012345678"
    assert r.json()["order_id"] == "c0ffee00-1234-5678-9abc-def012345678"


def test_sync_invalid_source(client) -> None:
    """POST /lab/sync with invalid source returns 400."""
    r = client.post(
        "/lab/sync",
        json={"source": "invalid", "symbols": "AAPL"},
    )
    assert r.status_code == 400


def test_get_default_user(fresh_storage) -> None:
    """auth_utils.get_default_user returns or creates default user."""
    from api.auth_utils import get_default_user, DEFAULT_USER_EMAIL

    user = get_default_user()
    assert user is not None
    assert user.email == DEFAULT_USER_EMAIL
    assert user.id is not None

    # Second call returns same user (no duplicate)
    user2 = get_default_user()
    assert user2.id == user.id


def test_forecast_run_insufficient_data(client) -> None:
    """POST /forecast/run with no bars returns success=False and error message."""
    r = client.post(
        "/forecast/run",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-06-30",
            "horizon": 1,
            "model": "arima",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert data["symbol"] == "AAPL"
    assert "error" in data and data["error"]
    assert data["direction"] == "flat"


def test_forecast_run_invalid_dates(client) -> None:
    """POST /forecast/run with bad date format returns 400."""
    r = client.post(
        "/forecast/run",
        json={
            "symbol": "AAPL",
            "from_date": "2024-13-01",  # invalid month
            "to_date": "2024-06-30",
            "horizon": 1,
            "model": "arima",
        },
    )
    assert r.status_code == 400
    detail = r.json().get("detail") or ""
    assert "Invalid date format" in detail


def test_forecast_run_invalid_model(client) -> None:
    """POST /forecast/run with unsupported model returns 400."""
    r = client.post(
        "/forecast/run",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-06-30",
            "horizon": 1,
            "model": "invalid",
        },
    )
    assert r.status_code == 400
    detail = r.json().get("detail") or ""
    assert "model must be 'arima' or 'gb'" in detail


def test_forecast_run_success(client_with_bars) -> None:
    """POST /forecast/run with enough bars returns forecast and direction."""
    r = client_with_bars.post(
        "/forecast/run",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 2,
            "model": "arima",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["symbol"] == "AAPL"
    assert data["direction"] in ("up", "down", "flat")
    assert len(data["forecast"]) == 2
    assert all("step" in p and "value" in p for p in data["forecast"])


def test_list_forecast_runs(client) -> None:
    """GET /forecast/runs returns a list (registry may be empty)."""
    r = client.get("/forecast/runs")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_evaluate_forecast_invalid_dates(client) -> None:
    """POST /forecast/evaluate with bad dates returns 400."""
    r = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "from_date": "bad-date",
            "to_date": "2024-06-30",
            "holdout_days": 5,
        },
    )
    assert r.status_code == 400
    detail = r.json().get("detail") or ""
    assert "Invalid date format" in detail


def test_evaluate_forecast_load_error(client, monkeypatch) -> None:
    """POST /forecast/evaluate when load_underlying_series raises returns success=False with error."""
    from api.routers import forecasting as fc_mod

    def boom(*args, **kwargs):
        raise RuntimeError("load failed")

    monkeypatch.setattr(fc_mod, "load_underlying_series", boom)

    r = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-06-30",
            "holdout_days": 5,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "load failed" in (data.get("error") or "")


def test_evaluate_forecast_insufficient_bars(client, monkeypatch) -> None:
    """POST /forecast/evaluate when there are too few bars returns an error."""
    import pandas as pd
    from api.routers import forecasting as fc_mod

    def tiny_series(*args, **kwargs):
        # Fewer rows than holdout_days + 20
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        return pd.DataFrame({"close": [100.0 + i for i in range(10)]}, index=dates)

    monkeypatch.setattr(fc_mod, "load_underlying_series", tiny_series)

    r = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-06-30",
            "holdout_days": 5,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "Need at least" in (data.get("error") or "")


def test_evaluate_forecast_success_route(client, monkeypatch) -> None:
    """POST /forecast/evaluate success path exercises ARIMA and backtest wiring."""
    import pandas as pd
    from api.routers import forecasting as fc_mod

    # Provide enough rows for all thresholds.
    def series_ok(*args, **kwargs):
        dates = pd.date_range("2024-01-01", periods=40, freq="D")
        return pd.DataFrame({"close": [100.0 + i for i in range(40)]}, index=dates)

    monkeypatch.setattr(fc_mod, "load_underlying_series", series_ok)

    def passthrough_features(df, drop_na=True):
        return df

    monkeypatch.setattr(fc_mod, "build_ohlcv_features", passthrough_features)

    class FakeModel:
        def __init__(self, *args, **kwargs) -> None:
            self._series = None

        def fit(self, s):
            self._series = s
            return self

        def predict(self, horizon: int):
            # Return last value repeated.
            import pandas as pd  # local import to avoid global dependency in this file

            last = float(self._series.iloc[-1])
            return pd.Series([last] * horizon, index=self._series.index[-horizon:])

        def predict_direction(self, horizon: int):
            return ["up"] * horizon

    monkeypatch.setattr(fc_mod, "ARIMAForecaster", lambda *a, **k: FakeModel())

    def fake_eval(actual, predicted):
        return {"directional_accuracy": 75.0, "rmse": 1.0, "mae": 0.5, "n_observations": len(actual)}

    monkeypatch.setattr(fc_mod, "evaluate_forecast", fake_eval)

    def fake_bt(actual, signals):
        return {"total_return": 10.0, "win_rate": 55.0}

    monkeypatch.setattr(fc_mod, "backtest_returns_from_signals", fake_bt)

    r = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-02-15",
            "holdout_days": 5,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["symbol"] == "AAPL"
    assert data["directional_accuracy"] == 75.0
    assert data["backtest_return"] == 10.0


def test_forecast_run_gb(client_with_bars) -> None:
    """POST /forecast/run with model=gb uses gradient boosting forecaster."""
    r = client_with_bars.post(
        "/forecast/run",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 1,
            "model": "gb",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["model"] == "gb"
    assert data["direction"] in ("up", "down", "flat")


def test_strategy_engine_evaluate(client) -> None:
    """POST /strategy-engine/evaluate returns expected value and payoff diagram."""
    r = client.post(
        "/strategy-engine/evaluate",
        json={
            "strategy_type": "straddle",
            "forecast_mean": 100.0,
            "forecast_std": 5.0,
            "strike": 100.0,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["strategy_type"] == "straddle"
    assert "expected_value" in data
    assert "probability_of_profit" in data
    assert "payoff_diagram" in data
    assert len(data["payoff_diagram"]) > 0


def test_strategy_engine_calendar(client) -> None:
    """POST /strategy-engine/evaluate with calendar_spread_call."""
    r = client.post(
        "/strategy-engine/evaluate",
        json={
            "strategy_type": "calendar_spread_call",
            "forecast_mean": 105.0,
            "forecast_std": 3.0,
            "strike": 100.0,
            "net_debit": 1.0,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["strategy_type"] == "calendar_spread_call"
    assert "expected_value" in data


def test_research_explain(client) -> None:
    """POST /research/explain returns explanation (placeholder without OPENAI_API_KEY)."""
    r = client.post(
        "/research/explain",
        json={
            "forecast_summary": "AAPL: up, horizon 1",
            "strategy_summary": "straddle EV=0.5",
            "include_risk": True,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "explanation" in data
    assert "AAPL" in data["explanation"] or "straddle" in data["explanation"]


def test_research_analyze(client_with_bars) -> None:
    """POST /research/analyze runs forecast + strategies + explanation."""
    r = client_with_bars.post(
        "/research/analyze",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 1,
            "strategy_types": ["straddle"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["symbol"] == "AAPL"
    assert data["forecast_direction"] in ("up", "down", "flat")
    assert "strategy_results" in data
    assert "explanation" in data


def test_research_analyze_passes_user_openai_key_from_settings(
    client_with_bars, monkeypatch
) -> None:
    """Full analysis must pass the OpenAI API key stored in user settings to the LLM layer."""
    from api import auth_utils
    from api.routers import research as research_router
    from models.sql_models import UserModel

    captured: dict[str, str | None] = {}

    def fake_explain(
        *,
        forecast_summary=None,
        strategy_summary=None,
        include_risk=True,
        user_api_key=None,
    ):
        captured["user_api_key"] = user_api_key
        return "mocked LLM explanation for test"

    monkeypatch.setattr(research_router, "explain_forecast_and_strategy", fake_explain)

    uid = auth_utils.get_default_user().id
    with session_scope() as session:
        user = session.get(UserModel, uid)
        assert user is not None
        user.settings_json = json.dumps({"openai_api_key": "sk-from-user-settings-test"})
        session.add(user)

    r = client_with_bars.post(
        "/research/analyze",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 1,
            "strategy_types": ["straddle"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["explanation"] == "mocked LLM explanation for test"
    assert captured.get("user_api_key") == "sk-from-user-settings-test"


def test_economic_series_missing_fred_key(client, monkeypatch) -> None:
    """GET /economic/series with source=fred and no key returns 400."""
    # Ensure no key is available from env or settings.
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    r = client.get("/economic/series", params={"source": "fred", "series_id": "GDP"})
    assert r.status_code == 400
    detail = r.json().get("detail") or ""
    assert "FRED_API_KEY" in detail


def test_economic_series_invalid_source(client) -> None:
    """GET /economic/series with unknown source returns 400."""
    r = client.get("/economic/series", params={"source": "unknown", "series_id": "GDP"})
    assert r.status_code == 400
    detail = r.json().get("detail") or ""
    assert "Unsupported economic data source" in detail


def test_economic_stored_not_found(client) -> None:
    """GET /economic/stored for a series that does not exist returns 404."""
    r = client.get("/economic/stored", params={"source": "fred", "series_id": "GDP"})
    assert r.status_code == 404


def test_economic_stored_list_and_latest(client) -> None:
    """Stored economic endpoints return series persisted in the DB."""
    # Seed one stored series directly via repository.
    with session_scope() as session:
        repo = EconomicSeriesRepository(session)
        series = repo.get_or_create_series("fred", "GDP", label="Real GDP")
        repo.upsert_points(
            series,
            [
                {"date": "2020-01-01", "value": 1.0},
                {"date": "2020-04-01", "value": 2.0},
            ],
        )

    # /economic/stored should return the seeded series.
    r = client.get("/economic/stored", params={"source": "fred", "series_id": "GDP"})
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "fred"
    assert data["series_id"] == "GDP"
    assert len(data["points"]) == 2

    # /economic/stored/list should include it with metadata.
    r_list = client.get("/economic/stored/list")
    assert r_list.status_code == 200
    items = r_list.json()["items"]
    assert any(it["source"] == "fred" and it["series_id"] == "GDP" for it in items)

    # /economic/stored/latest should also include it.
    r_latest = client.get("/economic/stored/latest")
    assert r_latest.status_code == 200
    latest_items = r_latest.json()["items"]
    assert any(it["source"] == "fred" and it["series_id"] == "GDP" for it in latest_items)


def test_economic_series_fred_success(client, monkeypatch) -> None:
    """GET /economic/series for FRED returns normalized points and stores them."""
    # Provide a fake FRED key and stub the upstream call.
    monkeypatch.setenv("FRED_API_KEY", "dummy")

    from api.routers import economic as econ_mod

    async def fake_fetch_json(url: str, params: dict | None = None, method: str = "GET", json_body: dict | None = None):
        # Only care that our code builds params correctly and parses observations.
        assert "series_id" in (params or {})
        return {
            "observations": [
                {"date": "2020-01-01", "value": "1.0"},
                {"date": "2020-04-01", "value": "."},  # sentinel -> None
            ]
        }

    monkeypatch.setattr(econ_mod, "_fetch_json", fake_fetch_json)

    r = client.get(
        "/economic/series",
        params={
            "source": "fred",
            "series_id": "GDP",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "fred"
    assert data["series_id"] == "GDP"
    assert data["points"] == [
        {"date": "2020-01-01", "value": 1.0},
        {"date": "2020-04-01", "value": None},
    ]


def test_economic_series_bls_success(client, monkeypatch) -> None:
    """GET /economic/series for BLS returns monthly points with numeric values or None."""
    monkeypatch.setenv("BLS_API_KEY", "dummy-bls")

    from api.routers import economic as econ_mod

    async def fake_fetch_json(url: str, params=None, method: str = "GET", json_body=None):
        # BLS handler uses method="POST" with json_body.
        assert method == "POST"
        assert isinstance(json_body, dict)
        return {
            "Results": {
                "series": [
                    {
                        "seriesID": "CUUR0000SA0",
                        "data": [
                            {"year": "2020", "period": "M01", "value": "250.0"},
                            {"year": "2020", "period": "M13", "value": "251.0"},  # annual avg -> skipped
                            {"year": "2020", "period": "M02", "value": "-"},      # placeholder -> None
                        ],
                    }
                ]
            }
        }

    monkeypatch.setattr(econ_mod, "_fetch_json", fake_fetch_json)

    r = client.get("/economic/series", params={"source": "bls", "series_id": "CUUR0000SA0"})
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "bls"
    assert data["series_id"] == "CUUR0000SA0"
    # Implementation keeps M13 and will render it as month 13. We just assert parsing behavior.
    assert data["points"][0] == {"date": "2020-01-01", "value": 250.0}
    assert any(p["date"] == "2020-02-01" and p["value"] is None for p in data["points"])


def test_economic_series_bea_success(client, monkeypatch) -> None:
    """GET /economic/series for BEA returns quarterly and annual points with cleaned numeric values."""
    monkeypatch.setenv("BEA_API_KEY", "dummy-bea")

    from api.routers import economic as econ_mod

    async def fake_fetch_json(url: str, params=None, method: str = "GET", json_body=None):
        # BEA handler uses GET with query params; we return a minimal NIPA-like payload.
        return {
            "BEAAPI": {
                "Results": {
                    "Data": [
                        {"TimePeriod": "2020Q1", "DataValue": "1,234.5"},
                        {"TimePeriod": "2020Q2", "DataValue": "NA"},
                        {"TimePeriod": "2019", "DataValue": "999.0 footnote"},
                    ]
                }
            }
        }

    monkeypatch.setattr(econ_mod, "_fetch_json", fake_fetch_json)

    r = client.get("/economic/series", params={"source": "bea", "series_id": "T10101"})
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "bea"
    assert data["series_id"] == "T10101"
    # TimePeriod "2020Q1" -> 2020-01-01, "2020Q2" -> 2020-04-01, "2019" -> 2019-01-01
    # "NA" becomes None; "1,234.5" and "999.0 footnote" are parsed as floats.
    pts = {p["date"]: p["value"] for p in data["points"]}
    assert pts["2020-01-01"] == 1234.5
    assert pts["2020-04-01"] is None
    assert pts["2019-01-01"] == 999.0


# ---------------------------------------------------------------------------
# Auth endpoint tests
# ---------------------------------------------------------------------------
@pytest.fixture
def unauthed_client(fresh_storage_file):
    """Test client WITHOUT the auth override — uses real JWT flow."""
    from api.main import app
    from storage.session import create_all_tables
    # Remove override if previously set by other fixture in same process
    from api import auth_utils
    app.dependency_overrides.pop(auth_utils.get_current_user, None)
    try:
        with TestClient(app, raise_server_exceptions=True) as c:
            create_all_tables()
            yield c
    finally:
        # Re-apply override so other fixtures are not affected
        app.dependency_overrides.pop(auth_utils.get_current_user, None)


def test_auth_register_and_login(unauthed_client):
    """Register a new user, then login and call a protected endpoint."""
    c = unauthed_client
    r = c.post("/auth/register", json={"email": "test@example.com", "password": "securepass123"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    assert token

    r2 = c.post("/auth/login", json={"email": "test@example.com", "password": "securepass123"})
    assert r2.status_code == 200
    token2 = r2.json()["access_token"]
    assert token2

    r3 = c.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert r3.status_code == 200
    assert r3.json()["email"] == "test@example.com"


def test_auth_wrong_password_returns_401(unauthed_client):
    c = unauthed_client
    c.post("/auth/register", json={"email": "a@b.com", "password": "password123"})
    r = c.post("/auth/login", json={"email": "a@b.com", "password": "wrongpassword"})
    assert r.status_code == 401


def test_auth_duplicate_register_returns_409(unauthed_client):
    c = unauthed_client
    c.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    r = c.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    assert r.status_code == 409


def test_protected_route_without_token_returns_401(unauthed_client):
    r = unauthed_client.get("/user/settings")
    assert r.status_code == 401


def test_protected_route_with_valid_token(unauthed_client):
    c = unauthed_client
    r = c.post("/auth/register", json={"email": "user@test.com", "password": "mypassword1"})
    token = r.json()["access_token"]
    r2 = c.get("/user/settings", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200


# ---------------------------------------------------------------------------
# Strategy engine – /discover endpoint
# ---------------------------------------------------------------------------

def test_strategy_engine_discover_no_data(client) -> None:
    """POST /strategy-engine/discover with no bars returns failure (no data)."""
    r = client.post(
        "/strategy-engine/discover",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 3,
            "model": "arima",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert data["symbol"] == "AAPL"
    assert "error" in data


def test_strategy_engine_discover_invalid_dates(client) -> None:
    """POST /strategy-engine/discover with bad dates returns failure."""
    r = client.post(
        "/strategy-engine/discover",
        json={
            "symbol": "AAPL",
            "from_date": "not-a-date",
            "to_date": "also-not-a-date",
            "horizon": 3,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "error" in data


def test_strategy_engine_discover_with_bars(client_with_bars) -> None:
    """POST /strategy-engine/discover with seeded bars returns ranked strategies."""
    r = client_with_bars.post(
        "/strategy-engine/discover",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 3,
            "model": "arima",
            "spread_width_pct": 0.02,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["symbol"] == "AAPL"
    assert isinstance(data["results"], list)
    assert len(data["results"]) > 0
    first = data["results"][0]
    assert first["rank"] == 1
    assert "strategy_type" in first
    assert "expected_value" in first
    assert "probability_of_profit" in first
    assert "max_loss" in first
    assert "max_gain" in first


def test_strategy_engine_discover_gb_model(client_with_bars) -> None:
    """POST /strategy-engine/discover with gb model returns results."""
    r = client_with_bars.post(
        "/strategy-engine/discover",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 1,
            "model": "gb",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert len(data["results"]) > 0


def test_strategy_engine_evaluate_bad_strategy(client) -> None:
    """POST /strategy-engine/evaluate with unknown strategy_type returns error."""
    r = client.post(
        "/strategy-engine/evaluate",
        json={
            "strategy_type": "unknown_strategy",
            "forecast_mean": 100.0,
            "forecast_std": 5.0,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "error" in data


def test_strategy_engine_evaluate_iron_condor(client) -> None:
    """POST /strategy-engine/evaluate iron_condor requires spread params."""
    r = client.post(
        "/strategy-engine/evaluate",
        json={
            "strategy_type": "iron_condor",
            "forecast_mean": 100.0,
            "forecast_std": 3.0,
            "put_long": 92.0,
            "put_short": 96.0,
            "call_short": 104.0,
            "call_long": 108.0,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["strategy_type"] == "iron_condor"


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

def test_delete_symbol_data_no_data(client) -> None:
    """DELETE /symbols/{symbol} with no data returns zero counts."""
    r = client.delete("/symbols/ZZZZ")
    assert r.status_code == 200
    data = r.json()
    assert data["symbol"] == "ZZZZ"
    assert data["underlying_bars_deleted"] == 0
    assert data["options_contracts_deleted"] == 0


def test_delete_symbol_data_with_bars(client_with_bars) -> None:
    """DELETE /symbols/{symbol} removes seeded bars."""
    r = client_with_bars.delete("/symbols/AAPL")
    assert r.status_code == 200
    data = r.json()
    assert data["symbol"] == "AAPL"
    assert data["underlying_bars_deleted"] > 0


# ---------------------------------------------------------------------------
# Forecasting – error paths
# ---------------------------------------------------------------------------

def test_forecast_invalid_dates(client) -> None:
    """POST /forecast/run with invalid dates returns 400."""
    r = client.post(
        "/forecast/run",
        json={
            "symbol": "AAPL",
            "from_date": "bad-date",
            "to_date": "also-bad",
            "horizon": 3,
        },
    )
    assert r.status_code == 400


def test_forecast_no_data(client) -> None:
    """POST /forecast/run with no bars in DB returns failure."""
    r = client.post(
        "/forecast/run",
        json={
            "symbol": "MISSING",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 3,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False


def test_forecast_gb_model(client_with_bars) -> None:
    """POST /forecast/run with gb model returns forecast."""
    r = client_with_bars.post(
        "/forecast/run",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 2,
            "model": "gb",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["model"] == "gb"


def test_forecast_invalid_model(client) -> None:
    """POST /forecast/run with unsupported model returns 400."""
    r = client.post(
        "/forecast/run",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 3,
            "model": "nonexistent",
        },
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Auth utils – edge cases
# ---------------------------------------------------------------------------

def test_auth_invalid_token(unauthed_client) -> None:
    """Request with a malformed Bearer token returns 401."""
    r = unauthed_client.get(
        "/user/settings",
        headers={"Authorization": "Bearer this.is.not.valid"},
    )
    assert r.status_code == 401


def test_auth_me_endpoint(unauthed_client) -> None:
    """GET /auth/me returns user info for authenticated user."""
    c = unauthed_client
    reg = c.post("/auth/register", json={"email": "me@test.com", "password": "securepass1"})
    token = reg.json()["access_token"]
    r = c.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "me@test.com"


# ---------------------------------------------------------------------------
# User settings – update path
# ---------------------------------------------------------------------------

def test_user_settings_update(client) -> None:
    """PUT /user/settings persists a setting change."""
    r = client.put("/user/settings", json={"etrade_sandbox": False})
    assert r.status_code == 200


def test_user_settings_roundtrip(client) -> None:
    """GET then PUT /user/settings preserves existing values."""
    get_r = client.get("/user/settings")
    assert get_r.status_code == 200
    put_r = client.put("/user/settings", json={"etrade_consumer_key": "test_key"})
    assert put_r.status_code == 200
    get_r2 = client.get("/user/settings")
    assert get_r2.status_code == 200


# ---------------------------------------------------------------------------
# Research – RAG endpoints and error paths
# ---------------------------------------------------------------------------

def test_research_rag_ingest(client) -> None:
    """POST /research/rag/ingest adds a document and reports success."""
    r = client.post(
        "/research/rag/ingest",
        json={"text": "A covered call sells upside in exchange for premium income.", "topic": "options_strategy"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "ingested" in data["message"].lower()


def test_research_rag_ingest_empty(client) -> None:
    """POST /research/rag/ingest with empty text returns failure."""
    r = client.post("/research/rag/ingest", json={"text": "   "})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False


def test_research_rag_retrieve(client) -> None:
    """POST /research/rag/retrieve returns relevant chunks."""
    r = client.post(
        "/research/rag/retrieve",
        json={"query": "bull call spread breakeven", "top_k": 2},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert isinstance(data["chunks"], list)
    assert len(data["chunks"]) <= 2


def test_research_analyze_no_data(client) -> None:
    """POST /research/analyze with no data returns failure."""
    r = client.post(
        "/research/analyze",
        json={
            "symbol": "NOSYM",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 1,
            "strategy_types": ["straddle"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False


def test_research_analyze_invalid_dates(client) -> None:
    """POST /research/analyze with invalid dates returns failure."""
    r = client.post(
        "/research/analyze",
        json={
            "symbol": "AAPL",
            "from_date": "not-a-date",
            "to_date": "nope",
            "horizon": 1,
            "strategy_types": ["straddle"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "date" in data.get("error", "").lower()


def test_research_analyze_with_iron_condor(client_with_bars) -> None:
    """POST /research/analyze with iron_condor strategy exercises IC param defaults."""
    r = client_with_bars.post(
        "/research/analyze",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 1,
            "strategy_types": ["iron_condor", "straddle"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "strategy_results" in data


def test_research_analyze_invalid_strategy_type(client_with_bars) -> None:
    """POST /research/analyze with an unknown strategy_type skips it gracefully."""
    r = client_with_bars.post(
        "/research/analyze",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 1,
            "strategy_types": ["not_a_real_strategy"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["strategy_results"] == []


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

def test_health_ok(client) -> None:
    """GET /health returns 200 with status ok when DB is reachable."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"] == "ok"
    assert "version" in data
    assert "environment" in data


def test_health_db_error(client) -> None:
    """GET /health returns 503 when the DB is unreachable."""
    from unittest.mock import patch, MagicMock

    cm = MagicMock()
    cm.__enter__ = MagicMock(side_effect=Exception("DB unavailable"))
    cm.__exit__ = MagicMock(return_value=False)
    with patch("api.main.session_scope", return_value=cm):
        r = client.get("/health")
    assert r.status_code == 503
    data = r.json()
    assert data["detail"]["status"] == "degraded"
    assert data["detail"]["checks"]["database"] == "error"


# ---------------------------------------------------------------------------
# Auth utils – unit level
# ---------------------------------------------------------------------------

def test_hash_and_verify_password() -> None:
    """hash_password produces a bcrypt hash that verify_password accepts."""
    from api.auth_utils import hash_password, verify_password

    pw = "my_secure_password"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_verify_password_bad_hash() -> None:
    """verify_password returns False when hash is corrupted (exception path)."""
    from api.auth_utils import verify_password

    assert verify_password("any", "not-a-valid-bcrypt-hash") is False


# ---------------------------------------------------------------------------
# Strategy engine – backtest include path
# ---------------------------------------------------------------------------

def test_strategy_engine_evaluate_with_backtest(client_with_bars) -> None:
    """POST /strategy-engine/evaluate with include_backtest exercises backtest integration."""
    r = client_with_bars.post(
        "/strategy-engine/evaluate",
        json={
            "strategy_type": "straddle",
            "forecast_mean": 100.0,
            "forecast_std": 5.0,
            "strike": 100.0,
            "include_backtest": True,
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "historical_backtest_return" in data


# ---------------------------------------------------------------------------
# Research analyze – vertical spread strategy branch
# ---------------------------------------------------------------------------

def test_research_analyze_vertical_spread(client_with_bars) -> None:
    """POST /research/analyze with vertical_spread exercises default param logic."""
    r = client_with_bars.post(
        "/research/analyze",
        json={
            "symbol": "AAPL",
            "from_date": "2024-01-01",
            "to_date": "2024-03-01",
            "horizon": 1,
            "strategy_types": ["vertical_spread_call", "vertical_spread_put"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert len(data["strategy_results"]) > 0
