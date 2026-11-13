import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infra.postgres.tables.base import Base


class UserProfessorHistory(Base):
    __tablename__ = "user_professor_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    country: Mapped[str] = mapped_column(String(120), nullable=False)
    profile_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    seen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "country",
            "profile_url",
            name="uq_user_professor_history_user_country_profile",
        ),
        Index(
            "idx_user_professor_history_lookup",
            "user_id",
            "country",
            "last_seen_at",
        ),
    )
