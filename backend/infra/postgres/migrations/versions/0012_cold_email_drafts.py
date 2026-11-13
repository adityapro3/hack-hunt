"""Create cold email drafts table.

Revision ID: 0012_cold_email_drafts
Revises: 0011_encrypt_api_keys
Create Date: 2026-04-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0012_cold_email_drafts"
down_revision: str | None = "0011_encrypt_api_keys"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cold_email_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="csrankings"),
        sa.Column("professor_name", sa.String(length=255), nullable=False),
        sa.Column("university_name", sa.String(length=255), nullable=True),
        sa.Column("profile_url", sa.String(length=1000), nullable=True),
        sa.Column("research_summary", sa.Text(), nullable=True),
        sa.Column("subject_line", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_cold_email_drafts_user_created",
        "cold_email_drafts",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_cold_email_drafts_user_created", table_name="cold_email_drafts")
    op.drop_table("cold_email_drafts")
