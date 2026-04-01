"""Alpaca paper trading routes: account, orders, cancel, and place orders."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api import auth_utils
from api.schemas import (
    AlpacaCancelRequest,
    EtradeCancelResponse,
    AlpacaEquityOrderRequest,
    AlpacaOptionOrderRequest,
)
from api.user_settings_utils import extract_unmasked_settings, load_user_settings
from brokers.alpaca_orders import (
    alpaca_cancel_order,
    alpaca_get_account,
    alpaca_list_orders,
    alpaca_place_equity_order,
    alpaca_place_option_order,
)
from models.sql_models import UserModel
from storage import session_scope

router = APIRouter(prefix="/lab/alpaca", tags=["lab", "alpaca"])


def _alpaca_creds_from_user(user) -> dict:
    data = load_user_settings(user)
    return extract_unmasked_settings(
        data,
        keys=("alpaca_api_key", "alpaca_api_secret"),
    )


def _broker_kwargs(creds: dict) -> dict:
    out = {}
    if creds.get("alpaca_api_key"):
        out["api_key"] = creds["alpaca_api_key"]
    if creds.get("alpaca_api_secret"):
        out["api_secret"] = creds["alpaca_api_secret"]
    return out


def _raise_broker_http_error(error: Exception) -> None:
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=str(error),
    )


@router.get("/accounts")
async def get_alpaca_accounts(
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _alpaca_creds_from_user(user) if user else {}
    kwargs = _broker_kwargs(creds)
    try:
        return alpaca_get_account(**kwargs)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        _raise_broker_http_error(e)


@router.get("/accounts/balance")
async def get_alpaca_account_balance(
    account_id_key: str | None = Query(None, description="Ignored for Alpaca paper trading"),
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _alpaca_creds_from_user(user) if user else {}
    kwargs = _broker_kwargs(creds)
    try:
        return alpaca_get_account(**kwargs)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        _raise_broker_http_error(e)


@router.get("/orders")
async def list_alpaca_orders(
    account_id_key: str | None = Query(None, description="Ignored for Alpaca paper trading"),
    status_param: str | None = Query(None, alias="status", description="OPEN, EXECUTED, CANCELLED, ALL"),
    count: int = Query(25, ge=1, le=100),
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _alpaca_creds_from_user(user) if user else {}
    kwargs = _broker_kwargs(creds)
    try:
        return alpaca_list_orders(count=count, status=status_param, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        _raise_broker_http_error(e)


@router.post("/orders/cancel", response_model=EtradeCancelResponse)
async def cancel_alpaca_order(
    body: AlpacaCancelRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _alpaca_creds_from_user(user) if user else {}
    kwargs = _broker_kwargs(creds)
    try:
        alpaca_cancel_order(str(body.order_id), **kwargs)
        return EtradeCancelResponse(
            success=True,
            account_id_key=body.account_id_key,
            order_id=body.order_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        _raise_broker_http_error(e)


@router.post("/orders/equity")
async def place_alpaca_equity_order(
    body: AlpacaEquityOrderRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _alpaca_creds_from_user(user) if user else {}
    kwargs = _broker_kwargs(creds)
    try:
        return alpaca_place_equity_order(
            body.symbol,
            body.order_action,
            body.quantity,
            price_type=body.price_type,
            limit_price=body.limit_price,
            stop_price=body.stop_price,
            **kwargs,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        _raise_broker_http_error(e)


@router.post("/orders/option")
async def place_alpaca_option_order(
    body: AlpacaOptionOrderRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _alpaca_creds_from_user(user) if user else {}
    kwargs = _broker_kwargs(creds)
    try:
        return alpaca_place_option_order(
            body.symbol,
            body.call_put,
            body.expiry_date,
            body.strike_price,
            body.order_action,
            body.quantity,
            price_type=body.price_type,
            limit_price=body.limit_price,
            **kwargs,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        _raise_broker_http_error(e)
