"""E*TRADE trading: list accounts, list/cancel orders, place equity/option orders. Uses user settings credentials."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api import auth_utils
from api.schemas import (
    EtradeCancelRequest,
    EtradeCancelResponse,
    EtradeEquityOrderRequest,
    EtradeOptionOrderRequest,
)
from api.user_settings_utils import extract_unmasked_settings, load_user_settings
from brokers.etrade_orders import (
    etrade_cancel_order,
    etrade_get_account_balance,
    etrade_list_accounts,
    etrade_list_orders,
    etrade_place_equity_order,
    etrade_place_option_order,
)
from models.sql_models import UserModel
from storage import session_scope

router = APIRouter(prefix="/lab/etrade", tags=["lab", "etrade"])


def _etrade_creds_from_user(user) -> dict:
    """E*TRADE credentials from user settings (for passing to broker)."""
    data = load_user_settings(user)
    creds = extract_unmasked_settings(
        data,
        keys=(
        "etrade_consumer_key",
        "etrade_consumer_secret",
        "etrade_access_token",
        "etrade_access_secret",
        "etrade_sandbox",
        ),
    )
    if "etrade_sandbox" in creds and not isinstance(creds["etrade_sandbox"], bool):
        creds.pop("etrade_sandbox", None)
    return creds


def _broker_kwargs(creds: dict, sandbox: bool | None) -> dict:
    """Build kwargs for get_etrade_accounts / get_etrade_order."""
    out = {}
    if sandbox is not None:
        out["sandbox"] = sandbox
    elif creds.get("etrade_sandbox") is not None:
        out["sandbox"] = creds["etrade_sandbox"]
    for key, attr in (
        ("etrade_consumer_key", "consumer_key"),
        ("etrade_consumer_secret", "consumer_secret"),
        ("etrade_access_token", "access_token"),
        ("etrade_access_secret", "access_secret"),
    ):
        if creds.get(key):
            out[attr] = creds[key]
    return out


def _raise_broker_http_error(error: Exception) -> None:
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=str(error),
    )


@router.get("/accounts")
async def list_etrade_accounts(
    sandbox: bool | None = Query(None, description="Override paper (true) vs live (false); else use Settings"),
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """List E*TRADE accounts. Uses credentials from Settings or env."""
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _etrade_creds_from_user(user) if user else {}
    kwargs = _broker_kwargs(creds, sandbox)
    try:
        return etrade_list_accounts(resp_format="json", **kwargs)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        _raise_broker_http_error(e)


@router.get("/accounts/balance")
async def get_etrade_account_balance(
    account_id_key: str = Query(..., description="E*TRADE account key"),
    account_type: str | None = Query(None, description="Optional account type"),
    real_time: bool = Query(True, description="Use real-time NAV values when available"),
    sandbox: bool | None = Query(None, description="Override paper (true) vs live (false); else use Settings"),
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Get E*TRADE balance/details for a specific account."""
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _etrade_creds_from_user(user) if user else {}
    kwargs = _broker_kwargs(creds, sandbox)
    try:
        return etrade_get_account_balance(
            account_id_key=account_id_key,
            account_type=account_type,
            real_time=real_time,
            resp_format="json",
            **kwargs,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        _raise_broker_http_error(e)


@router.get("/orders")
async def list_etrade_orders(
    account_id_key: str = Query(..., description="E*TRADE account key"),
    status: str | None = Query(None, description="OPEN, EXECUTED, CANCELLED, etc."),
    count: int = Query(25, ge=1, le=100),
    sandbox: bool | None = Query(None),
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """List orders for an E*TRADE account."""
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _etrade_creds_from_user(user) if user else {}
    kwargs = _broker_kwargs(creds, sandbox)
    try:
        return etrade_list_orders(
            account_id_key,
            count=count,
            status=status,
            resp_format="json",
            **kwargs,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        _raise_broker_http_error(e)


@router.post("/orders/cancel", response_model=EtradeCancelResponse)
async def cancel_etrade_order(
    body: EtradeCancelRequest,
    sandbox: bool | None = Query(None),
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Cancel an E*TRADE order."""
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _etrade_creds_from_user(user) if user else {}
    kwargs = _broker_kwargs(creds, sandbox)
    try:
        # Request XML from the broker layer because E*TRADE cancel responses may
        # not always be valid JSON even on success. We normalize the result into
        # a small stable JSON payload for the frontend.
        etrade_cancel_order(
            body.account_id_key,
            int(body.order_id),
            resp_format="xml",
            **kwargs,
        )
        return EtradeCancelResponse(
            success=True,
            account_id_key=body.account_id_key,
            order_id=body.order_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )


@router.post("/orders/equity")
async def place_etrade_equity_order(
    body: EtradeEquityOrderRequest,
    sandbox: bool | None = Query(None),
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Place an E*TRADE equity order (BUY/SELL)."""
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _etrade_creds_from_user(user) if user else {}
    broker_kw = _broker_kwargs(creds, sandbox)
    try:
        return etrade_place_equity_order(
            body.account_id_key,
            body.symbol,
            body.order_action,
            body.quantity,
            price_type=body.price_type,
            limit_price=body.limit_price,
            stop_price=body.stop_price,
            **broker_kw,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        _raise_broker_http_error(e)


@router.post("/orders/option")
async def place_etrade_option_order(
    body: EtradeOptionOrderRequest,
    sandbox: bool | None = Query(None),
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Place an E*TRADE single-leg option order."""
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        creds = _etrade_creds_from_user(user) if user else {}
    broker_kw = _broker_kwargs(creds, sandbox)
    try:
        return etrade_place_option_order(
            body.account_id_key,
            body.symbol,
            body.call_put.upper(),
            body.expiry_date[:10],
            body.strike_price,
            body.order_action,
            body.quantity,
            price_type=body.price_type,
            limit_price=body.limit_price,
            **broker_kw,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        _raise_broker_http_error(e)
