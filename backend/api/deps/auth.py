from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.infra.postgres.session import get_db
from backend.infra.postgres.tables import User
from backend.security import decode_access_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/signin")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user_id = decode_access_token(token)
    except ValueError as exc:
        raise credentials_error from exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise credentials_error

    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
