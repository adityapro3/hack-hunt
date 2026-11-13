"""Set user cold-email profile provider default to oppora_free.

Revision ID: 0021_profile_provider_default_oppora_free
Revises: 0020_free_tier_usage_counters
Create Date: 2026-04-16
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0021_provider_oppora_free"
down_revision: str | None = "0020_free_tier_usage_counters"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE user_coldemail_profiles "
        "ALTER COLUMN profile_provider SET DEFAULT 'oppora_free'"
    )
    op.execute(
        "UPDATE user_coldemail_profiles "
        "SET profile_provider = 'oppora_free' "
        "WHERE profile_provider = 'platform_ollama_cloud'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE user_coldemail_profiles "
        "ALTER COLUMN profile_provider SET DEFAULT 'platform_ollama_cloud'"
    )
    op.execute(
        "UPDATE user_coldemail_profiles "
        "SET profile_provider = 'platform_ollama_cloud' "
        "WHERE profile_provider = 'oppora_free'"
    )
