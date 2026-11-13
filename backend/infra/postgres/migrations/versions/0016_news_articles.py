"""Add news_articles table for latest-news ingestion.

Revision ID: 0016_news_articles
Revises: 0015_coldemail_profiles_research
Create Date: 2026-04-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision: str = "0016_news_articles"
down_revision: str | None = "0015_coldemail_profiles_research"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False, server_default="english"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("url", name="uq_news_articles_url"),
    )
    op.create_index("idx_news_articles_topic", "news_articles", ["topic"], unique=False)
    op.create_index("idx_news_articles_source", "news_articles", ["source"], unique=False)
    op.create_index("idx_news_articles_published", "news_articles", ["published_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_news_articles_published", table_name="news_articles")
    op.drop_index("idx_news_articles_source", table_name="news_articles")
    op.drop_index("idx_news_articles_topic", table_name="news_articles")
    op.drop_table("news_articles")
