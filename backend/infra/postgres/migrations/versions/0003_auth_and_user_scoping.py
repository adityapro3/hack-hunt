"""Add users table, auth support, and per-user data scoping.

Revision ID: 0003_auth_and_user_scoping
Revises: 0002_phase2_tables
Create Date: 2026-04-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_auth_and_user_scoping"
down_revision: str | None = "0002_phase2_tables"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("password_hash", sa.String(length=500), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("idx_users_email", "users", ["email"], unique=False)

    op.add_column("bookmarks", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_bookmarks_user_id_users",
        "bookmarks",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("uq_bookmark_opportunity", "bookmarks", type_="unique")
    op.create_unique_constraint("uq_bookmark_user_opportunity", "bookmarks", ["user_id", "opportunity_id"])
    op.create_index("idx_bookmarks_user_id", "bookmarks", ["user_id"], unique=False)

    op.add_column("applications", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_applications_user_id_users",
        "applications",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("uq_application_opportunity", "applications", type_="unique")
    op.create_unique_constraint("uq_application_user_opportunity", "applications", ["user_id", "opportunity_id"])
    op.create_index("idx_applications_user_id", "applications", ["user_id"], unique=False)

    op.add_column("user_settings", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_user_settings_user_id_users",
        "user_settings",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("ck_user_settings_single_row", "user_settings", type_="check")
    op.create_unique_constraint("uq_user_settings_user_id", "user_settings", ["user_id"])


def downgrade() -> None:
    op.drop_constraint("uq_user_settings_user_id", "user_settings", type_="unique")
    op.create_check_constraint("ck_user_settings_single_row", "user_settings", "id = 1")
    op.drop_constraint("fk_user_settings_user_id_users", "user_settings", type_="foreignkey")
    op.drop_column("user_settings", "user_id")

    op.drop_index("idx_applications_user_id", table_name="applications")
    op.drop_constraint("uq_application_user_opportunity", "applications", type_="unique")
    op.create_unique_constraint("uq_application_opportunity", "applications", ["opportunity_id"])
    op.drop_constraint("fk_applications_user_id_users", "applications", type_="foreignkey")
    op.drop_column("applications", "user_id")

    op.drop_index("idx_bookmarks_user_id", table_name="bookmarks")
    op.drop_constraint("uq_bookmark_user_opportunity", "bookmarks", type_="unique")
    op.create_unique_constraint("uq_bookmark_opportunity", "bookmarks", ["opportunity_id"])
    op.drop_constraint("fk_bookmarks_user_id_users", "bookmarks", type_="foreignkey")
    op.drop_column("bookmarks", "user_id")

    op.drop_index("idx_users_email", table_name="users")
    op.drop_table("users")
