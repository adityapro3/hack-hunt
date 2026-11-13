"""Add Ollama Cloud settings fields.

Revision ID: 0009_user_settings_ollama_cloud
Revises: 0008_user_settings_saved_models
Create Date: 2026-04-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0009_user_settings_ollama_cloud"
down_revision: str | None = "0008_user_settings_saved_models"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("ollama_cloud_api_key", sa.String(length=500), nullable=True))
    op.add_column(
        "user_settings",
        sa.Column(
            "ollama_cloud_base_url",
            sa.String(length=500),
            nullable=False,
            server_default=sa.text("'https://api.ollama.com'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "ollama_cloud_base_url")
    op.drop_column("user_settings", "ollama_cloud_api_key")
