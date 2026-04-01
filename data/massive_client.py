"""Massive.com REST client wrapper. API key from env only."""

from massive import RESTClient

from config import get_massive_api_key


def get_massive_client(api_key: str | None = None) -> RESTClient:
    """Return RESTClient. Uses api_key arg or MASSIVE_API_KEY env."""
    key = api_key or get_massive_api_key()
    if not key:
        raise ValueError(
            "Massive API key required. Set MASSIVE_API_KEY env or pass api_key=..."
        )
    return RESTClient(api_key=key)
