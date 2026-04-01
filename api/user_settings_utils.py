"""Helpers for reading and filtering user settings JSON."""

from __future__ import annotations

import json
from typing import Any

from api.schemas import SETTINGS_MASK
from models.sql_models import UserModel


def load_user_settings(user: UserModel | None) -> dict[str, Any]:
    """Load settings JSON from user record; return empty dict on invalid data."""
    if not user or not user.settings_json:
        return {}
    try:
        data = json.loads(user.settings_json)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_user_settings(user: UserModel, data: dict[str, Any]) -> None:
    """Persist normalized settings map back to JSON storage."""
    user.settings_json = json.dumps(data)


def extract_unmasked_settings(
    data: dict[str, Any],
    *,
    keys: tuple[str, ...],
) -> dict[str, Any]:
    """Extract selected keys, excluding masked values and nulls."""
    out: dict[str, Any] = {}
    for key in keys:
        value = data.get(key)
        if value is None or value == SETTINGS_MASK:
            continue
        out[key] = value
    return out
