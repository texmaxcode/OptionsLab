"""Tests for data/massive_client."""

import pytest

from data.massive_client import get_massive_client


def test_get_massive_client_with_key():
    client = get_massive_client(api_key="test_key_123")
    assert client is not None


def test_get_massive_client_no_key_raises(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Massive API key required"):
        get_massive_client()


def test_get_massive_client_from_env(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "env_key")
    client = get_massive_client()
    assert client is not None
