"""Add cold-email student profile and professor research cache tables.

Revision ID: 0015_coldemail_profiles_research
Revises: 0014_embed_model_nomic
Create Date: 2026-04-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0015_coldemail_profiles_research"
down_revision: str | None = "0014_embed_model_nomic"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "professor_research_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="arxiv"),
        sa.Column("professor_name", sa.String(length=255), nullable=False),
        sa.Column("university_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("publications_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("publication_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "professor_name",
            "university_name",
            name="uq_professor_research_source_prof_univ",
        ),
    )
    op.create_index(
        "idx_professor_research_lookup",
        "professor_research_cache",
        ["professor_name", "university_name"],
        unique=False,
    )

    op.create_table(
        "user_coldemail_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_filename", sa.String(length=255), nullable=True),
        sa.Column("resume_text", sa.Text(), nullable=False),
        sa.Column("profile_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("profile_provider", sa.String(length=50), nullable=False, server_default="platform_ollama_cloud"),
        sa.Column("profile_model", sa.String(length=120), nullable=False, server_default="gemma4:31b-it"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_coldemail_profile_user"),
    )

    op.add_column(
        "cold_email_drafts",
        sa.Column("ask_type", sa.String(length=50), nullable=False, server_default="phd_inquiry"),
    )


def downgrade() -> None:
    op.drop_column("cold_email_drafts", "ask_type")

    op.drop_table("user_coldemail_profiles")

    op.drop_index("idx_professor_research_lookup", table_name="professor_research_cache")
    op.drop_table("professor_research_cache")
