import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infra.postgres.tables.base import Base


class ProfessorResearchCache(Base):
    __tablename__ = "professor_research_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="arxiv", server_default="arxiv")
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    professor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    university_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    publications_json: Mapped[list[dict]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    publication_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_professor_research_country", "country"),
        Index(
            "idx_professor_research_lookup",
            "professor_name",
            "university_name",
        ),
    )
