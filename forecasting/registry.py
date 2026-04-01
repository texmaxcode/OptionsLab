"""
Lightweight model registry for forecast runs.

Stores metadata (model_id, symbol, horizon, model_type, metrics) in a JSON file
so the Research Assistant and API can cite which model was used. Does not persist
model artifacts (weights); use a separate path/bucket for that if needed.
"""

import json
import os
import uuid
from pathlib import Path
from typing import Any


def _registry_path() -> Path:
    """Path to the registry JSON file. Configurable via env."""
    default = Path(os.environ.get("TRADING_DATA_DIR", ".")) / "forecast_registry.json"
    return Path(os.environ.get("TRADING_FORECAST_REGISTRY", str(default)))


def register_forecast_run(
    symbol: str,
    from_date: str,
    to_date: str,
    horizon: int,
    model_type: str,
    metrics: dict[str, Any] | None = None,
    *,
    model_id: str | None = None,
) -> str:
    """
    Append a forecast run to the registry. Returns the model_id (new UUID if not provided).

    Args:
        symbol: Underlying symbol.
        from_date: Train start (YYYY-MM-DD).
        to_date: Train end (YYYY-MM-DD).
        horizon: Forecast horizon in periods.
        model_type: e.g. "arima", "gb".
        metrics: Optional dict (e.g. rmse, directional_accuracy, backtest_return).
        model_id: Optional id; if None, a new UUID is generated.
    """
    mid = model_id or str(uuid.uuid4())
    entry = {
        "model_id": mid,
        "symbol": symbol,
        "from_date": from_date,
        "to_date": to_date,
        "horizon": horizon,
        "model_type": model_type,
        "metrics": metrics or {},
    }
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    if path.exists():
        try:
            with open(path) as f:
                records = json.load(f)
        except (json.JSONDecodeError, OSError):
            records = []
    records.append(entry)
    with open(path, "w") as f:
        json.dump(records, f, indent=2)
    return mid


def list_forecast_runs(
    symbol: str | None = None,
    model_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Return registered forecast runs, optionally filtered by symbol and model_type.
    Most recent last (append order). Limit number of results.
    """
    path = _registry_path()
    if not path.exists():
        return []
    try:
        with open(path) as f:
            records = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if symbol is not None:
        records = [r for r in records if r.get("symbol") == symbol]
    if model_type is not None:
        records = [r for r in records if r.get("model_type") == model_type]
    return records[-limit:]
