import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infra.postgres.tables.base import Base


class ColdEmailDraft(Base):
    __tablename__ = "cold_email_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    country: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="csrankings", nullable=False)
    professor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    university_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    research_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_line: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    tone: Mapped[str] = mapped_column(String(50), nullable=False)
    ask_type: Mapped[str] = mapped_column(String(50), default="phd_inquiry", nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_cold_email_drafts_user_created", "user_id", "created_at"),
    )
