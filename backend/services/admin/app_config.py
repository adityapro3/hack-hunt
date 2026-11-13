from datetime import datetime
from collections.abc import Callable
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.infra.postgres.tables import UserSettings


def record_admin_log(
    logs: list[str],
    message: str,
    emit_log: Callable[[str], None] | None = None,
) -> None:
    timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}"
    logs.append(line)
    if emit_log is not None:
        emit_log(line)
    

def get_embedding_base_url(db: Session, user_id: str | None = None) -> str:
    """Gets the embedding base URL (Ollama URL) from user settings."""
    if user_id:
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = db.execute(stmt).scalar_one_or_none()
        if settings and settings.ollama_base_url:
            return settings.ollama_base_url

