"""Add country/profile URL to professor research cache and user professor history.

Revision ID: 0019_professor_research_cache_country_profile_url
Revises: 0018_drop_app_config
Create Date: 2026-04-15
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0019_add_country_profile_url"
down_revision: str | None = "0018_drop_app_config"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("professor_research_cache", sa.Column("country", sa.String(length=120), nullable=True))
    op.add_column("professor_research_cache", sa.Column("profile_url", sa.String(length=1000), nullable=True))
    op.drop_constraint(
        "uq_professor_research_source_prof_univ",
        "professor_research_cache",
        type_="unique",
    )
    op.create_index(
        "idx_professor_research_country",
        "professor_research_cache",
        ["country"],
        unique=False,
    )

    op.create_table(
        "user_professor_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country", sa.String(length=120), nullable=False),
        sa.Column("profile_url", sa.String(length=1000), nullable=False),
        sa.Column("seen_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id",
            "country",
            "profile_url",
            name="uq_user_professor_history_user_country_profile",
        ),
    )

    conn = op.get_bind()
    draft_rows = conn.execute(
        sa.text(
            """
            SELECT user_id, lower(country) AS country, profile_url, count(*) AS seen_count, max(created_at) AS last_seen_at
            FROM cold_email_drafts
            WHERE profile_url IS NOT NULL
            GROUP BY user_id, lower(country), profile_url
            """
        )
    ).mappings().all()
    if draft_rows:
        history_table = sa.table(
            "user_professor_history",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("user_id", postgresql.UUID(as_uuid=True)),
            sa.column("country", sa.String(length=120)),
            sa.column("profile_url", sa.String(length=1000)),
            sa.column("seen_count", sa.Integer()),
            sa.column("last_seen_at", sa.DateTime(timezone=True)),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        )
        op.bulk_insert(
            history_table,
            [
                {
                    "id": uuid4(),
                    "user_id": row["user_id"],
                    "country": row["country"],
                    "profile_url": row["profile_url"],
                    "seen_count": row["seen_count"],
                    "last_seen_at": row["last_seen_at"],
                    "created_at": row["last_seen_at"],
                    "updated_at": row["last_seen_at"],
                }
                for row in draft_rows
            ],
        )

    op.create_index(
        "idx_user_professor_history_lookup",
        "user_professor_history",
        ["user_id", "country", "last_seen_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_user_professor_history_lookup", table_name="user_professor_history")
    op.drop_table("user_professor_history")

    op.drop_index("idx_professor_research_country", table_name="professor_research_cache")
    op.drop_column("professor_research_cache", "profile_url")
    op.drop_column("professor_research_cache", "country")
    op.create_unique_constraint(
        "uq_professor_research_source_prof_univ",
        "professor_research_cache",
        ["professor_name", "university_name"],
    )

