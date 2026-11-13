"""Drop persisted Ollama Cloud base URL from user settings.

Revision ID: 0010_drop_ollama_cloud_url
Revises: 0009_user_settings_ollama_cloud
Create Date: 2026-04-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0010_drop_ollama_cloud_url"
down_revision: str | None = "0009_user_settings_ollama_cloud"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("user_settings", "ollama_cloud_base_url")


def downgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "ollama_cloud_base_url",
            sa.String(length=500),
            nullable=False,
            server_default=sa.text("'https://api.ollama.com'"),
        ),
    )
