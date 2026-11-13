import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infra.postgres.tables.base import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    gemini_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    openai_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    anthropic_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    ollama_model: Mapped[str] = mapped_column(String(100), default="llama3.2", nullable=False)
    ollama_base_url: Mapped[str] = mapped_column(String(500), default="http://localhost:11434", nullable=False)
    ollama_cloud_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    free_scribe_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    free_seer_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    saved_models: Mapped[dict[str, list[str]]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (UniqueConstraint("user_id", name="uq_user_settings_user_id"),)
