"""Tests for the macro/economic feature loader and join utilities."""

import pandas as pd
import pytest
from datetime import datetime

from features.macro_features import load_macro_features, join_macro_features


# ---------------------------------------------------------------------------
# join_macro_features – pure DataFrame logic, no DB needed
# ---------------------------------------------------------------------------

def _ohlcv(n: int = 10, start: str = "2024-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=n, freq="D")
    return pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0 + pd.Series(range(n), dtype=float).values,
            "volume": 1000,
        },
        index=dates,
    )


def test_join_empty_macro_returns_ohlcv_unchanged() -> None:
    ohlcv = _ohlcv(5)
    result = join_macro_features(ohlcv, pd.DataFrame())
    assert result.shape == ohlcv.shape
    assert list(result.columns) == list(ohlcv.columns)


def test_join_empty_ohlcv_returns_empty() -> None:
    macro = pd.DataFrame({"macro_gdp": [1.0]}, index=pd.DatetimeIndex(["2024-01-01"]))
    result = join_macro_features(pd.DataFrame(), macro)
    assert result.empty


def test_join_adds_macro_prefix_columns() -> None:
    ohlcv = _ohlcv(5)
    macro = pd.DataFrame(
        {"gdp": [21.0, 21.5]},
        index=pd.DatetimeIndex(["2024-01-01", "2024-01-06"]),
    )
    result = join_macro_features(ohlcv, macro)
    assert "macro_gdp" in result.columns
    assert "close" in result.columns


def test_join_forward_fills_monthly_macro_to_daily() -> None:
    ohlcv = _ohlcv(10, "2024-01-01")
    # Macro has only one monthly point at the start
    macro = pd.DataFrame(
        {"gdp": [100.0]},
        index=pd.DatetimeIndex(["2024-01-01"]),
    )
    result = join_macro_features(ohlcv, macro, fill_method="ffill")
    # All rows should have the macro value forward-filled
    assert result["macro_gdp"].notna().sum() > 0
    assert result["macro_gdp"].iloc[0] == 100.0


def test_join_fills_later_rows_with_ffill() -> None:
    """After a macro reading, forward-filled value should persist on subsequent rows."""
    ohlcv = _ohlcv(5, "2024-01-01")
    macro = pd.DataFrame(
        {"rate": [5.5]},
        index=pd.DatetimeIndex(["2024-01-01"]),
    )
    result = join_macro_features(ohlcv, macro)
    filled = result["macro_rate"].dropna()
    assert len(filled) >= 1
    assert filled.iloc[0] == pytest.approx(5.5)


def test_join_preserves_original_ohlcv_values() -> None:
    ohlcv = _ohlcv(5)
    macro = pd.DataFrame({"x": [1.0]}, index=pd.DatetimeIndex(["2024-01-01"]))
    result = join_macro_features(ohlcv, macro)
    pd.testing.assert_series_equal(result["close"], ohlcv["close"])


def test_join_custom_prefix() -> None:
    ohlcv = _ohlcv(3)
    macro = pd.DataFrame({"gdp": [1.0]}, index=pd.DatetimeIndex(["2024-01-01"]))
    result = join_macro_features(ohlcv, macro, prefix="econ_")
    assert "econ_gdp" in result.columns
    assert "macro_gdp" not in result.columns


def test_join_multiple_macro_series() -> None:
    ohlcv = _ohlcv(5)
    macro = pd.DataFrame(
        {"gdp": [20.0, 21.0], "cpi": [3.1, 3.2]},
        index=pd.DatetimeIndex(["2024-01-01", "2024-01-04"]),
    )
    result = join_macro_features(ohlcv, macro)
    assert "macro_gdp" in result.columns
    assert "macro_cpi" in result.columns


# ---------------------------------------------------------------------------
# load_macro_features – requires DB access via fresh_storage fixture
# ---------------------------------------------------------------------------

def test_load_macro_features_empty_db_returns_empty(fresh_storage) -> None:
    """With no economic data synced, load_macro_features should return an empty DataFrame."""
    result = load_macro_features("2024-01-01", "2024-12-31")
    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_load_macro_features_returns_dataframe(fresh_storage) -> None:
    """Return type is always a DataFrame even when DB is empty."""
    result = load_macro_features()
    assert isinstance(result, pd.DataFrame)


def test_load_macro_features_with_stored_series(fresh_storage) -> None:
    """With data in the DB, load_macro_features returns a wide DataFrame."""
    from models.sql_models import EconomicSeriesModel, EconomicSeriesPointModel
    from storage import session_scope

    with session_scope() as sess:
        series = EconomicSeriesModel(source="fred", series_id="TESTGDP", label="Test GDP")
        sess.add(series)
        sess.flush()
        for i in range(3):
            point = EconomicSeriesPointModel(
                series_id_fk=series.id,
                date=datetime(2024, 1 + i, 1),
                value=float(100 + i),
            )
            sess.add(point)

    result = load_macro_features("2024-01-01", "2024-12-31")
    assert not result.empty
    assert "fred_TESTGDP" in result.columns
    assert result["fred_TESTGDP"].notna().sum() > 0


def test_load_macro_features_series_id_filter(fresh_storage) -> None:
    """series_ids filter restricts which series are loaded."""
    from models.sql_models import EconomicSeriesModel, EconomicSeriesPointModel
    from storage import session_scope

    with session_scope() as sess:
        for sid in ("A", "B"):
            series = EconomicSeriesModel(source="fred", series_id=sid, label=sid)
            sess.add(series)
            sess.flush()
            sess.add(EconomicSeriesPointModel(
                series_id_fk=series.id,
                date=datetime(2024, 1, 1),
                value=1.0,
            ))

    # Filter to only series "A"
    result = load_macro_features("2024-01-01", "2024-12-31", series_ids=["A"])
    assert "fred_A" in result.columns
    assert "fred_B" not in result.columns
