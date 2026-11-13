from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.infra.postgres.tables import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def create_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    password_hash: str,
    is_admin: bool,
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        full_name=full_name,
        password_hash=password_hash,
        is_admin=is_admin,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
