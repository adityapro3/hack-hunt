"""Add saved_models to user settings.

Revision ID: 0008_user_settings_saved_models
Revises: 0007_embedding_dimension_768
Create Date: 2026-04-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008_user_settings_saved_models"
down_revision: str | None = "0007_embedding_dimension_768"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "saved_models",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "saved_models")
