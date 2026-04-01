"""E*TRADE OAuth 1.0a flow.

The UI collects only:
- consumer key
- consumer secret

Then we:
1) request an OAuth request token
2) redirect user to the authorization URL (out-of-band "oob" callback)
3) exchange the OAuth verifier for an access token + access secret
4) store access_token/access_secret in the user's settings_json
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pyetrade.authorization import ETradeAccessManager
from requests_oauthlib import OAuth1Session

from api import auth_utils
from api.schemas import (
    EtradeOAuthDisconnectResponse,
    EtradeOAuthExchangeAccessTokenRequest,
    EtradeOAuthExchangeAccessTokenResponse,
    EtradeOAuthRequestTokenResponse,
)
from api.user_settings_utils import load_user_settings as _load_user_settings, save_user_settings as _save_user_settings
from config import get_etrade_sandbox
from models.sql_models import UserModel
from storage import session_scope

router = APIRouter(prefix="/lab/etrade/oauth", tags=["lab", "etrade", "oauth"])


SETTINGS_KEY_CONSUMER_KEY = "etrade_consumer_key"
SETTINGS_KEY_CONSUMER_SECRET = "etrade_consumer_secret"
SETTINGS_KEY_SANDBOX = "etrade_sandbox"
SETTINGS_KEY_ACCESS_TOKEN = "etrade_access_token"
SETTINGS_KEY_ACCESS_SECRET = "etrade_access_secret"

# Stored only between the "request token" step and the "exchange access token" step.
SETTINGS_KEY_REQUEST_TOKEN = "etrade_oauth_request_token"
SETTINGS_KEY_REQUEST_TOKEN_SECRET = "etrade_oauth_request_token_secret"

_AUTH_URL = "https://us.etrade.com/e/t/etws/authorize"
def _oauth_endpoints(*, sandbox: bool) -> tuple[str, str]:
    """Return (request_token_url, access_token_url)."""
    if sandbox:
        return (
            "https://apisb.etrade.com/oauth/request_token",
            "https://apisb.etrade.com/oauth/access_token",
        )
    return (
        "https://api.etrade.com/oauth/request_token",
        "https://api.etrade.com/oauth/access_token",
    )


def _oauth_error_detail(action: str, error: Exception, *, sandbox: bool) -> str:
    message = str(error)
    if "consumer_key_rejected" in message:
        if sandbox:
            return (
                f"Failed to {action}: E*TRADE rejected the consumer key in Paper mode. "
                "Production keys do not work against the sandbox endpoint. "
                "Switch E*TRADE mode to Live and try again."
            )
        return (
            f"Failed to {action}: E*TRADE rejected the consumer key in Live mode. "
            "Verify you pasted the production consumer key/secret pair correctly and that the app is approved for live access in the E*TRADE developer portal."
        )
    return f"Failed to {action}: {error}"


@router.post("/request-token", response_model=EtradeOAuthRequestTokenResponse)
async def request_etrade_request_token(
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Start OAuth flow: fetch request token and return authorization URL."""
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        data = _load_user_settings(user)

        consumer_key = data.get(SETTINGS_KEY_CONSUMER_KEY) or None
        consumer_secret = data.get(SETTINGS_KEY_CONSUMER_SECRET) or None
        sandbox = data.get(SETTINGS_KEY_SANDBOX)
        sandbox_val = sandbox if isinstance(sandbox, bool) else get_etrade_sandbox()

        if not consumer_key or not consumer_secret:
            raise HTTPException(
                status_code=400,
                detail="E*TRADE consumer key/secret missing. Set them in Settings first.",
            )

        req_token_url, _access_token_url = _oauth_endpoints(sandbox=sandbox_val)

        # OAuth 1.0a out-of-band: user will get a verifier code to paste back.
        oauth = OAuth1Session(
            consumer_key,
            consumer_secret,
            callback_uri="oob",
            signature_type="AUTH_HEADER",
        )

        try:
            request_token = oauth.fetch_request_token(req_token_url)
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=_oauth_error_detail("request token", e, sandbox=sandbox_val),
            ) from e

        request_oauth_token = request_token.get("oauth_token")
        request_oauth_token_secret = request_token.get("oauth_token_secret")

        if not request_oauth_token or not request_oauth_token_secret:
            raise HTTPException(status_code=502, detail="E*TRADE did not return request token secrets.")

        # Persist request token + secret until verifier exchange.
        data[SETTINGS_KEY_REQUEST_TOKEN] = request_oauth_token
        data[SETTINGS_KEY_REQUEST_TOKEN_SECRET] = request_oauth_token_secret
        _save_user_settings(user, data)
        session.add(user)

    authorization_url = f"{_AUTH_URL}?key={consumer_key}&token={request_oauth_token}"
    return EtradeOAuthRequestTokenResponse(
        authorization_url=authorization_url,
        sandbox=bool(sandbox_val),
    )


@router.post("/exchange-access-token", response_model=EtradeOAuthExchangeAccessTokenResponse)
async def exchange_etrade_access_token(
    body: EtradeOAuthExchangeAccessTokenRequest,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Exchange OAuth verifier for access token + secret and store it."""
    verifier = (body.verifier or "").strip()
    if not verifier:
        raise HTTPException(status_code=400, detail="Verifier is required.")

    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        data = _load_user_settings(user)

        consumer_key = data.get(SETTINGS_KEY_CONSUMER_KEY) or None
        consumer_secret = data.get(SETTINGS_KEY_CONSUMER_SECRET) or None
        sandbox = data.get(SETTINGS_KEY_SANDBOX)
        sandbox_val = sandbox if isinstance(sandbox, bool) else get_etrade_sandbox()

        request_token = data.get(SETTINGS_KEY_REQUEST_TOKEN) or None
        request_token_secret = data.get(SETTINGS_KEY_REQUEST_TOKEN_SECRET) or None

        if not consumer_key or not consumer_secret:
            raise HTTPException(
                status_code=400,
                detail="E*TRADE consumer key/secret missing. Set them in Settings first.",
            )
        if not request_token or not request_token_secret:
            raise HTTPException(
                status_code=400,
                detail="No pending OAuth request token found. Start the flow again (request-token).",
            )

        _req_token_url, access_token_url = _oauth_endpoints(sandbox=bool(sandbox_val))

        oauth = OAuth1Session(
            consumer_key,
            consumer_secret,
            resource_owner_key=request_token,
            resource_owner_secret=request_token_secret,
            signature_type="AUTH_HEADER",
        )

        # requests_oauthlib expects verifier stored on the underlying OAuth client.
        try:
            oauth._client.client.verifier = verifier  # type: ignore[attr-defined]
        except Exception:
            pass

        try:
            token_data = oauth.fetch_access_token(access_token_url)
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=_oauth_error_detail("exchange access token", e, sandbox=bool(sandbox_val)),
            ) from e

        access_token = token_data.get("oauth_token") or token_data.get("access_token")
        access_secret = token_data.get("oauth_token_secret") or token_data.get("access_secret")

        if not access_token or not access_secret:
            raise HTTPException(status_code=502, detail="E*TRADE did not return access tokens.")

        data[SETTINGS_KEY_ACCESS_TOKEN] = access_token
        data[SETTINGS_KEY_ACCESS_SECRET] = access_secret
        # Clear pending request token fields after success.
        data.pop(SETTINGS_KEY_REQUEST_TOKEN, None)
        data.pop(SETTINGS_KEY_REQUEST_TOKEN_SECRET, None)

        _save_user_settings(user, data)
        session.add(user)

    return EtradeOAuthExchangeAccessTokenResponse(success=True)


@router.post("/disconnect", response_model=EtradeOAuthDisconnectResponse)
async def disconnect_etrade(
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Disconnect E*TRADE by revoking the access token when possible and clearing stored tokens."""
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        data = _load_user_settings(user)

        consumer_key = data.get(SETTINGS_KEY_CONSUMER_KEY) or None
        consumer_secret = data.get(SETTINGS_KEY_CONSUMER_SECRET) or None
        access_token = data.get(SETTINGS_KEY_ACCESS_TOKEN) or None
        access_secret = data.get(SETTINGS_KEY_ACCESS_SECRET) or None

        # Best-effort revoke: clear local tokens even if upstream revoke fails.
        if consumer_key and consumer_secret and access_token and access_secret:
            try:
                ETradeAccessManager(
                    client_key=consumer_key,
                    client_secret=consumer_secret,
                    resource_owner_key=access_token,
                    resource_owner_secret=access_secret,
                ).revoke_access_token()
            except Exception:
                pass

        for key in (
            SETTINGS_KEY_ACCESS_TOKEN,
            SETTINGS_KEY_ACCESS_SECRET,
            SETTINGS_KEY_REQUEST_TOKEN,
            SETTINGS_KEY_REQUEST_TOKEN_SECRET,
        ):
            data.pop(key, None)

        _save_user_settings(user, data)
        session.add(user)

    return EtradeOAuthDisconnectResponse(success=True)

