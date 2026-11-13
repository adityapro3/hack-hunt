"""Add bookmarks, applications, and user settings tables.

Revision ID: 0002_phase2_tables
Revises: 0001_initial_opportunities
Create Date: 2026-04-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase2_tables"
down_revision: str | None = "0001_initial_opportunities"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bookmarks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("opportunity_id", name="uq_bookmark_opportunity"),
    )

    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=30), server_default=sa.text("'interested'"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("opportunity_id", name="uq_application_opportunity"),
    )

    op.create_index("idx_applications_status", "applications", ["status"])

    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gemini_api_key", sa.String(length=500), nullable=True),
        sa.Column("openai_api_key", sa.String(length=500), nullable=True),
        sa.Column("anthropic_api_key", sa.String(length=500), nullable=True),
        sa.Column("ollama_model", sa.String(length=100), server_default=sa.text("'llama3.2'"), nullable=False),
        sa.Column(
            "ollama_base_url",
            sa.String(length=500),
            server_default=sa.text("'http://localhost:11434'"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_user_settings_single_row"),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
    op.drop_index("idx_applications_status", table_name="applications")
    op.drop_table("applications")
    op.drop_table("bookmarks")
