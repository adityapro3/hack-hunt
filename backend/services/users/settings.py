from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.infra.postgres.tables import UserSettings


def get_or_create_settings(db: Session, user_id: UUID) -> UserSettings:
    row = db.execute(select(UserSettings).where(UserSettings.user_id == user_id)).scalar_one_or_none()
    if row:
        return row

    row = UserSettings(user_id=user_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
