"""Initial opportunities schema.

Revision ID: 0001_initial_opportunities
Revises:
Create Date: 2026-04-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_opportunities"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "opportunities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("opportunity_type", sa.String(length=30), nullable=False, server_default=sa.text("'hackathon'")),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("title_normalized", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("domains", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("skills", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=True),
        sa.Column("location", sa.String(length=300), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prize_money", sa.String(length=200), nullable=True),
        sa.Column("registration_fee", sa.String(length=100), nullable=True),
        sa.Column("team_size", sa.String(length=50), nullable=True),
        sa.Column("eligibility", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("embedding", Vector(dim=384), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("title_normalized", "source", name="uq_opportunity_title_source"),
    )

    op.create_index("idx_opportunities_status", "opportunities", ["status"])
    op.create_index("idx_opportunities_mode", "opportunities", ["mode"])
    op.create_index("idx_opportunities_deadline", "opportunities", ["deadline"])
    op.create_index("idx_opportunities_domains", "opportunities", ["domains"], postgresql_using="gin")
    op.create_index("idx_opportunities_skills", "opportunities", ["skills"], postgresql_using="gin")
    op.execute(
        "CREATE INDEX idx_opportunities_embedding ON opportunities USING ivfflat (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("idx_opportunities_embedding", table_name="opportunities")
    op.drop_index("idx_opportunities_skills", table_name="opportunities")
    op.drop_index("idx_opportunities_domains", table_name="opportunities")
    op.drop_index("idx_opportunities_deadline", table_name="opportunities")
    op.drop_index("idx_opportunities_mode", table_name="opportunities")
    op.drop_index("idx_opportunities_status", table_name="opportunities")
    op.drop_table("opportunities")
