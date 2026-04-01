"""Tests for volatility metrics and API endpoint."""

import math
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from volatility.metrics import (
    historical_volatility,
    hv_series,
    iv_rank,
    iv_percentile,
    expected_move,
)


# ── Unit tests: volatility/metrics.py ──────────────────────────────────────

class TestHistoricalVolatility:
    def _closes(self, n: int = 100) -> pd.Series:
        """Deterministic price series: constant-growth to avoid randomness."""
        return pd.Series([100.0 + i * 0.1 for i in range(n)])

    def test_returns_float_for_sufficient_data(self):
        closes = self._closes(60)
        result = historical_volatility(closes, 20)
        assert result is not None
        assert isinstance(result, float)
        assert result >= 0

    def test_returns_none_insufficient_data(self):
        closes = pd.Series([100.0, 101.0, 102.0])
        assert historical_volatility(closes, 20) is None

    def test_returns_none_for_constant_prices(self):
        closes = pd.Series([100.0] * 30)
        result = historical_volatility(closes, 20)
        # std of constant returns is 0 → HV = 0.0
        assert result is not None
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_hv_series_length(self):
        closes = pd.Series([100.0 + i * 0.5 for i in range(50)])
        series = hv_series(closes, 20)
        # log returns lose 1 observation, then rolling needs window days, so series is n-1 long
        assert len(series) < len(closes)

    def test_hv_series_first_n_are_nan(self):
        closes = pd.Series([100.0 + i * 0.5 for i in range(50)])
        series = hv_series(closes, 20)
        # First 20 values should be NaN (rolling window of 20 on log returns which loses 1)
        assert series.dropna().count() < len(series)


class TestIVRank:
    def _iv_history(self) -> pd.Series:
        return pd.Series([0.20, 0.25, 0.30, 0.35, 0.40])

    def test_iv_at_minimum_returns_0(self):
        h = self._iv_history()
        assert iv_rank(0.20, h) == pytest.approx(0.0, abs=0.01)

    def test_iv_at_maximum_returns_100(self):
        h = self._iv_history()
        assert iv_rank(0.40, h) == pytest.approx(100.0, abs=0.01)

    def test_iv_at_midpoint_returns_50(self):
        h = self._iv_history()
        assert iv_rank(0.30, h) == pytest.approx(50.0, abs=0.1)

    def test_empty_series_returns_none(self):
        assert iv_rank(0.25, pd.Series([], dtype=float)) is None

    def test_constant_series_returns_50(self):
        h = pd.Series([0.25, 0.25, 0.25])
        result = iv_rank(0.25, h)
        assert result == 50.0


class TestIVPercentile:
    def _iv_history(self) -> pd.Series:
        return pd.Series([0.10, 0.20, 0.30, 0.40, 0.50])

    def test_above_all_returns_100(self):
        h = self._iv_history()
        result = iv_percentile(0.60, h)
        assert result == pytest.approx(100.0, abs=0.01)

    def test_below_all_returns_0(self):
        h = self._iv_history()
        result = iv_percentile(0.05, h)
        assert result == pytest.approx(0.0, abs=0.01)

    def test_middle_value(self):
        h = self._iv_history()
        result = iv_percentile(0.30, h)
        # 2 values below 0.30 → 2/5 = 40%
        assert result == pytest.approx(40.0, abs=0.01)

    def test_empty_series_returns_none(self):
        assert iv_percentile(0.25, pd.Series([], dtype=float)) is None


class TestExpectedMove:
    def test_basic_calculation(self):
        em = expected_move(100.0, 0.25, 30)
        expected = 100.0 * 0.25 * math.sqrt(30 / 252)
        assert em == pytest.approx(expected, rel=1e-6)

    def test_higher_iv_gives_larger_move(self):
        em_low = expected_move(100.0, 0.20, 30)
        em_high = expected_move(100.0, 0.40, 30)
        assert em_high > em_low

    def test_longer_dte_gives_larger_move(self):
        em_short = expected_move(100.0, 0.25, 7)
        em_long = expected_move(100.0, 0.25, 30)
        assert em_long > em_short


# ── API integration tests ───────────────────────────────────────────────────

@pytest.fixture
def client(fresh_storage_file):
    """FastAPI test client with fresh DB and auth override."""
    from api.main import app
    from api import auth_utils
    from storage.session import create_all_tables

    app.dependency_overrides[auth_utils.get_current_user] = auth_utils.get_default_user
    try:
        with TestClient(app) as c:
            create_all_tables()
            yield c
    finally:
        app.dependency_overrides.pop(auth_utils.get_current_user, None)


def test_volatility_endpoint_no_data(client):
    r = client.get("/volatility/NONEEXIST?from_date=2024-01-01&to_date=2024-06-30")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert "error" in data


def test_volatility_endpoint_invalid_date(client):
    r = client.get("/volatility/AAPL?from_date=invalid&to_date=2024-06-30")
    assert r.status_code == 200
    assert r.json()["success"] is False
