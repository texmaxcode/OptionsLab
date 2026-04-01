"""Tests for brokers/alpaca_orders."""

from unittest.mock import MagicMock, patch

import pytest

from brokers.alpaca_orders import _occ_option_symbol, alpaca_get_account, alpaca_place_option_order


def test_alpaca_get_account_raises_without_creds(monkeypatch):
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="Alpaca paper trading credentials"):
        alpaca_get_account()


def test_occ_option_symbol_formats_alpaca_symbol():
    assert _occ_option_symbol("AAPL", "CALL", "2026-01-16", 195.0) == "AAPL260116C00195000"
    assert _occ_option_symbol("aapl", "PUT", "2026-01-16", 195.5) == "AAPL260116P00195500"


def test_alpaca_place_option_order_uses_occ_symbol(monkeypatch):
    monkeypatch.setenv("APCA_API_KEY_ID", "ak")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "as")

    response = MagicMock()
    response.status_code = 200
    response.text = '{"id":"paper-order-id"}'
    response.json.return_value = {"id": "paper-order-id"}
    response.raise_for_status.return_value = None

    with patch("brokers.alpaca_orders.requests.request", return_value=response) as mock_request:
        result = alpaca_place_option_order(
            "AAPL",
            "CALL",
            "2026-01-16",
            195.0,
            "BUY_OPEN",
            2,
            price_type="LIMIT",
            limit_price=1.25,
        )

    assert result["id"] == "paper-order-id"
    kwargs = mock_request.call_args.kwargs
    assert kwargs["json"]["symbol"] == "AAPL260116C00195000"
    assert kwargs["json"]["qty"] == 2
    assert kwargs["json"]["side"] == "buy"
    assert kwargs["json"]["type"] == "limit"
