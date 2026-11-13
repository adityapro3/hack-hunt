"""Add persistent free-tier usage counters to user_settings.

Revision ID: 0020_free_tier_usage_counters
Revises: 0019_add_country_profile_url
Create Date: 2026-04-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0020_free_tier_usage_counters"
down_revision: str | None = "0019_add_country_profile_url"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("free_scribe_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_settings",
        sa.Column("free_seer_used", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "free_seer_used")
    op.drop_column("user_settings", "free_scribe_used")
