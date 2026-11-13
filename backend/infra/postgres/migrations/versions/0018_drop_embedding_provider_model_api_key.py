"""Drop app_config table as settings are moved to user_settings.

Revision ID: 0018_drop_app_config
Revises: 0017_drop_unused_news_columns
Create Date: 2026-04-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0018_drop_app_config"
down_revision: str | None = "0017_drop_unused_news_columns"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("app_config")


def downgrade() -> None:
    op.create_table(
        "app_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=20), server_default=sa.text("'ollama'"), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), server_default=sa.text("'nomic-ai/nomic-embed-text-v1.5'"), nullable=False),
        sa.Column("embedding_base_url", sa.String(length=500), nullable=True),
        sa.Column("embedding_api_key", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_app_config_single_row"),
    )
