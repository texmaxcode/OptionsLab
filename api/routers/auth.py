"""POST /auth/register and POST /auth/login — user registration and JWT login."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from api.auth_utils import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from api.schemas import AuthUserInfo, LoginRequest, RegisterRequest, TokenResponse
from models.sql_models import UserModel, utcnow_naive
from storage import session_scope

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    """Create a new user account and return a JWT."""
    with session_scope() as session:
        existing = session.execute(
            select(UserModel).where(UserModel.email == body.email)
        ).scalars().one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        user = UserModel(
            email=body.email,
            password_hash=hash_password(body.password),
            created_at=utcnow_naive(),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    """Validate credentials and return a JWT."""
    with session_scope() as session:
        user = session.execute(
            select(UserModel).where(UserModel.email == body.email)
        ).scalars().one_or_none()
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        user.last_login_at = utcnow_naive()
        session.commit()
        token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=AuthUserInfo)
def me(current_user: UserModel = Depends(get_current_user)):
    """Return the currently authenticated user's info."""
    return AuthUserInfo(id=current_user.id, email=current_user.email)
