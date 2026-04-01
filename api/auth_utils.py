"""Authentication utilities: JWT creation, verification, and FastAPI dependencies."""

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy import select

from models.sql_models import UserModel, utcnow_naive
from storage import session_scope

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_HOURS = 24
_DEV_FALLBACK_SECRET = "dev-secret-key-change-in-production-please"

DEFAULT_USER_EMAIL = "default@local"

# Module-level cache so Secrets Manager is called at most once per cold start.
_jwt_secret_cache: str | None = None


def _jwt_secret() -> str:
    """Return the JWT signing key.

    Resolution order:
      1. ``JWT_SECRET_KEY_ARN`` env var → fetch from AWS Secrets Manager
         (set by CDK ApiStack in Lambda deployments).
      2. ``JWT_SECRET_KEY`` env var → plain string secret.
      3. Hard-coded dev fallback — **never use in production**.
    """
    global _jwt_secret_cache
    if _jwt_secret_cache is not None:
        return _jwt_secret_cache

    secret_arn = os.environ.get("JWT_SECRET_KEY_ARN")
    if secret_arn:
        try:
            import boto3  # available in Lambda runtime; optional locally
            client = boto3.client("secretsmanager")
            resp = client.get_secret_value(SecretId=secret_arn)
            _jwt_secret_cache = resp.get("SecretString") or resp.get("SecretBinary", b"").decode()
            return _jwt_secret_cache
        except Exception:
            # Fall through — e.g. running locally without AWS credentials
            pass

    _jwt_secret_cache = os.environ.get("JWT_SECRET_KEY", _DEV_FALLBACK_SECRET)
    return _jwt_secret_cache


# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=_ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, _jwt_secret(), algorithm=_ALGORITHM)


def _decode_token(token: str) -> int:
    """Return user_id from a valid token or raise 401."""
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[_ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise ValueError("missing sub")
        return int(sub)
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserModel:
    """FastAPI dependency: validate Bearer token and return the UserModel."""
    user_id = _decode_token(token)
    with session_scope() as session:
        user = session.get(UserModel, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user


# ---------------------------------------------------------------------------
# Legacy / test helper
# ---------------------------------------------------------------------------
def get_default_user() -> UserModel:
    """Return the synthetic default user (get or create). Used in tests only."""
    with session_scope() as session:
        user = session.execute(
            select(UserModel).where(UserModel.email == DEFAULT_USER_EMAIL)
        ).scalars().one_or_none()
        if user is None:
            user = UserModel(
                email=DEFAULT_USER_EMAIL,
                password_hash=hash_password("default-local"),
                created_at=utcnow_naive(),
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        return user
