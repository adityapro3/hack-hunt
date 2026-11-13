"""Add global app configuration table.

Revision ID: 0005_app_config_table
Revises: 0004_opportunity_enums
Create Date: 2026-04-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_app_config_table"
down_revision: str | None = "0004_opportunity_enums"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=20), server_default=sa.text("'huggingface'"), nullable=False),
        sa.Column(
            "embedding_model",
            sa.String(length=200),
            server_default=sa.text("'sentence-transformers/all-MiniLM-L6-v2'"),
            nullable=False,
        ),
        sa.Column("embedding_base_url", sa.String(length=500), nullable=True),
        sa.Column("embedding_api_key", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_app_config_single_row"),
    )



def downgrade() -> None:
    op.drop_table("app_config")
