"""Tests for brokers/etrade_orders."""

from unittest.mock import MagicMock, patch

import pytest

from brokers.etrade_orders import (
    get_etrade_order,
    etrade_list_accounts,
    etrade_list_orders,
    etrade_cancel_order,
)


def test_get_etrade_order_raises_without_creds(monkeypatch):
    monkeypatch.delenv("ETrade_CONSUMER_KEY", raising=False)
    with pytest.raises(ValueError, match="E*TRADE credentials"):
        get_etrade_order()


def test_get_etrade_order_with_creds(etrade_env):
    with patch("brokers.etrade_orders.ETradeOrder") as mock_order:
        get_etrade_order(sandbox=True)
        mock_order.assert_called_once()


def test_etrade_list_accounts(etrade_env):
    with patch("brokers.etrade_orders.get_etrade_accounts") as mock_get:
        mock_acc = MagicMock()
        mock_acc.list_accounts.return_value = {"AccountListResponse": {}}
        mock_get.return_value = mock_acc
        result = etrade_list_accounts(resp_format="json")
        assert "AccountListResponse" in result


def test_etrade_list_orders(etrade_env):
    with patch("brokers.etrade_orders.get_etrade_order") as mock_get:
        mock_ord = MagicMock()
        mock_ord.list_orders.return_value = {"OrdersResponse": {}}
        mock_get.return_value = mock_ord
        result = etrade_list_orders("account_key_123", count=10, resp_format="json")
        assert "OrdersResponse" in result
        mock_ord.list_orders.assert_called_once()


def test_etrade_cancel_order(etrade_env):
    with patch("brokers.etrade_orders.get_etrade_order") as mock_get:
        mock_ord = MagicMock()
        mock_ord.cancel_order.return_value = {"CancelOrderResponse": {}}
        mock_get.return_value = mock_ord
        etrade_cancel_order("account_key", 12345, resp_format="json")
        mock_ord.cancel_order.assert_called_once_with(account_id_key="account_key", order_num=12345, resp_format="json")


def test_etrade_place_equity_order(etrade_env):
    from brokers.etrade_orders import etrade_place_equity_order
    with patch("brokers.etrade_orders.get_etrade_order") as mock_get:
        mock_ord = MagicMock()
        mock_ord.place_equity_order.return_value = {"PlaceOrderResponse": {}}
        mock_get.return_value = mock_ord
        etrade_place_equity_order("acc_key", "AAPL", "BUY", 10, price_type="MARKET")
        mock_ord.place_equity_order.assert_called_once()


def test_etrade_place_option_order(etrade_env):
    from brokers.etrade_orders import etrade_place_option_order
    with patch("brokers.etrade_orders.get_etrade_order") as mock_get:
        mock_ord = MagicMock()
        mock_ord.place_option_order.return_value = {"PlaceOrderResponse": {}}
        mock_ord.preview_equity_order.return_value = {"PreviewOrderResponse": {"PreviewIds": {"previewId": 999}}}
        mock_get.return_value = mock_ord
        etrade_place_option_order("acc_key", "AAPL", "CALL", "2025-01-17", 200.0, "BUY_OPEN", 1)
        mock_ord.place_option_order.assert_called_once()
