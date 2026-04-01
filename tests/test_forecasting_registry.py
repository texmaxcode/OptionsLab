"""Tests for the forecast run registry."""

import os
import tempfile

from forecasting.registry import register_forecast_run, list_forecast_runs


def test_register_and_list_forecast_runs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "reg.json")
        os.environ["TRADING_FORECAST_REGISTRY"] = path
        try:
            mid = register_forecast_run(
                symbol="AAPL",
                from_date="2024-01-01",
                to_date="2024-06-01",
                horizon=5,
                model_type="arima",
                metrics={"rmse": 0.02},
            )
            assert mid
            runs = list_forecast_runs()
            assert len(runs) == 1
            assert runs[0]["symbol"] == "AAPL"
            assert runs[0]["model_type"] == "arima"
            assert runs[0]["metrics"].get("rmse") == 0.02
            runs_filtered = list_forecast_runs(symbol="AAPL", model_type="arima")
            assert len(runs_filtered) == 1
            assert list_forecast_runs(symbol="MSFT") == []
        finally:
            os.environ.pop("TRADING_FORECAST_REGISTRY", None)
