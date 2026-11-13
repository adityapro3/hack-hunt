"""Convert opportunities type/status to enums and sanitize descriptions.

Revision ID: 0004_opportunity_enums
Revises: 0003_auth_and_user_scoping
Create Date: 2026-04-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_opportunity_enums"
down_revision: str | None = "0003_auth_and_user_scoping"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    opportunity_type_enum = postgresql.ENUM(
        "Job",
        "Hackathon",
        "Conference",
        name="opportunity_type_enum",
    )
    opportunity_status_enum = postgresql.ENUM(
        "Active",
        "Upcoming",
        name="opportunity_status_enum",
    )

    opportunity_type_enum.create(bind, checkfirst=True)
    opportunity_status_enum.create(bind, checkfirst=True)

    op.alter_column(
        "opportunities",
        "opportunity_type",
        existing_type=sa.String(length=30),
        server_default=None,
    )
    op.alter_column(
        "opportunities",
        "status",
        existing_type=sa.String(length=20),
        server_default=None,
    )

    op.alter_column(
        "opportunities",
        "opportunity_type",
        existing_type=sa.String(length=30),
        type_=opportunity_type_enum,
        nullable=False,
        postgresql_using=(
            "CASE "
            "WHEN lower(opportunity_type) = 'job' THEN 'Job' "
            "WHEN lower(opportunity_type) = 'conference' THEN 'Conference' "
            "ELSE 'Hackathon' "
            "END::opportunity_type_enum"
        ),
        server_default=sa.text("'Hackathon'"),
    )

    op.alter_column(
        "opportunities",
        "status",
        existing_type=sa.String(length=20),
        type_=opportunity_status_enum,
        nullable=False,
        postgresql_using=(
            "CASE "
            "WHEN lower(status) = 'upcoming' THEN 'Upcoming' "
            "ELSE 'Active' "
            "END::opportunity_status_enum"
        ),
        server_default=sa.text("'Active'"),
    )

    op.execute(
        """
        UPDATE opportunities
        SET description = NULLIF(
            btrim(
                regexp_replace(
                    regexp_replace(description, E'[#*_`]+', '', 'g'),
                    E'\\s+',
                    ' ',
                    'g'
                )
            ),
            ''
        )
        WHERE description IS NOT NULL
        """
    )


def downgrade() -> None:
    bind = op.get_bind()

    opportunity_status_enum = postgresql.ENUM(
        "Active",
        "Upcoming",
        name="opportunity_status_enum",
    )
    opportunity_type_enum = postgresql.ENUM(
        "Job",
        "Hackathon",
        "Conference",
        name="opportunity_type_enum",
    )

    op.alter_column(
        "opportunities",
        "status",
        existing_type=opportunity_status_enum,
        server_default=None,
    )
    op.alter_column(
        "opportunities",
        "opportunity_type",
        existing_type=opportunity_type_enum,
        server_default=None,
    )

    op.alter_column(
        "opportunities",
        "status",
        existing_type=opportunity_status_enum,
        type_=sa.String(length=20),
        nullable=False,
        postgresql_using="lower(status::text)",
        server_default=sa.text("'active'"),
    )

    op.alter_column(
        "opportunities",
        "opportunity_type",
        existing_type=opportunity_type_enum,
        type_=sa.String(length=30),
        nullable=False,
        postgresql_using="lower(opportunity_type::text)",
        server_default=sa.text("'hackathon'"),
    )

    opportunity_status_enum.drop(bind, checkfirst=True)
    opportunity_type_enum.drop(bind, checkfirst=True)
