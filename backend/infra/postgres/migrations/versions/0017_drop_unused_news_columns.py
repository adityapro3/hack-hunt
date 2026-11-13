"""Drop unused normalized title and summary columns from news_articles.

Revision ID: 0017_drop_unused_news_columns
Revises: 0016_news_articles
Create Date: 2026-04-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0017_drop_unused_news_columns"
down_revision: str | None = "0016_news_articles"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE news_articles DROP COLUMN IF EXISTS title_normalized")
    op.execute("ALTER TABLE news_articles DROP COLUMN IF EXISTS summary")


def downgrade() -> None:
    op.add_column("news_articles", sa.Column("title_normalized", sa.String(length=500), nullable=True))
    op.add_column("news_articles", sa.Column("summary", sa.Text(), nullable=True))
