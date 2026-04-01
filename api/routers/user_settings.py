"""User settings routes."""

from fastapi import APIRouter, Depends

from api import auth_utils
from api.schemas import UserSettings, UserSettingsUpdate, SETTINGS_MASK
from api.user_settings_utils import load_user_settings, save_user_settings
from models.sql_models import UserModel
from storage import session_scope


router = APIRouter(prefix="/user", tags=["user"])

CREDENTIAL_KEYS = (
    "massive_api_key",
    "alpaca_api_key",
    "alpaca_api_secret",
    "etrade_consumer_key",
    "etrade_consumer_secret",
    "etrade_oauth_request_token",
    "etrade_oauth_request_token_secret",
    "etrade_access_token",
    "etrade_access_secret",
    "fred_api_key",
    "bls_api_key",
    "bea_api_key",
    "openai_api_key",
)


def _mask_credentials(data: dict) -> dict:
    """Replace credential values with mask for GET response."""
    out = dict(data)
    for k in CREDENTIAL_KEYS:
        if k in out and out[k] and out[k] != SETTINGS_MASK:
            out[k] = SETTINGS_MASK
    return out


@router.get("/settings", response_model=UserSettings)
async def get_settings(current_user: UserModel = Depends(auth_utils.get_current_user)):
    """Return user settings, or defaults if none stored. Credentials are masked."""
    data = load_user_settings(current_user)
    return UserSettings(**_mask_credentials(data))


@router.put("/settings", response_model=UserSettings)
async def update_settings(
    body: UserSettingsUpdate,
    current_user: UserModel = Depends(auth_utils.get_current_user),
):
    """Update and persist user settings. Credentials: send real value to set, omit or send mask to keep."""
    with session_scope() as session:
        user = session.get(UserModel, current_user.id)
        if user is None:
            return UserSettings()
        existing = load_user_settings(user)
        body_dict = body.model_dump(exclude_unset=True)
        merged = dict(existing)
        for k, v in body_dict.items():
            if k in CREDENTIAL_KEYS:
                if v and v != SETTINGS_MASK:
                    merged[k] = v
            else:
                merged[k] = v
        save_user_settings(user, merged)
        session.add(user)
    return UserSettings(**_mask_credentials(merged))

