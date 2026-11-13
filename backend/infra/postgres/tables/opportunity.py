import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum as SAEnum, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.opportunity_enums import OpportunityStatus, OpportunityType
from backend.infra.postgres.tables.base import Base


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_type: Mapped[OpportunityType] = mapped_column(
        SAEnum(OpportunityType, name="opportunity_type_enum", native_enum=True),
        default=OpportunityType.Hackathon,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_normalized: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    domains: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    skills: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)

    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    prize_money: Mapped[str | None] = mapped_column(String(200), nullable=True)
    registration_fee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    team_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    eligibility: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    status: Mapped[OpportunityStatus] = mapped_column(
        SAEnum(OpportunityStatus, name="opportunity_status_enum", native_enum=True),
        default=OpportunityStatus.Active,
        nullable=False,
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("title_normalized", "source", name="uq_opportunity_title_source"),
        Index("idx_opportunities_status", "status"),
        Index("idx_opportunities_mode", "mode"),
        Index("idx_opportunities_deadline", "deadline"),
        Index("idx_opportunities_domains", "domains", postgresql_using="gin"),
        Index("idx_opportunities_skills", "skills", postgresql_using="gin"),
    )
