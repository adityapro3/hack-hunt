from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps.auth import get_current_user
from backend.core.config import get_settings
from backend.infra.postgres.session import get_db
from backend.infra.postgres.tables import User
from backend.schemas import AuthResponse, SignInRequest, SignUpRequest, UserResponse
from backend.security import create_access_token, hash_password, verify_password
from backend.services.users.auth_query import create_user, get_user_by_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def sign_up(payload: SignUpRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    existing = get_user_by_email(db=db, email=email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    settings = get_settings()
    is_admin = False
    if payload.admin_signup_key is not None:
        if not settings.admin_signup_key or payload.admin_signup_key != settings.admin_signup_key:
            raise HTTPException(status_code=403, detail="Invalid admin signup key")
        is_admin = True

    user = create_user(
        db=db,
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_admin=is_admin,
        is_active=True,
    )

    access_token = create_access_token(user.id)
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=_to_user_response(user),
    )


@router.post("/signin", response_model=AuthResponse)
def sign_in(payload: SignInRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = get_user_by_email(db=db, email=email)

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    access_token = create_access_token(user.id)
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=_to_user_response(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return _to_user_response(current_user)
