"""Add delivery workflow fields to cold email drafts.

Revision ID: 0013_cold_email_delivery_fields
Revises: 0012_cold_email_drafts
Create Date: 2026-04-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0013_cold_email_delivery_fields"
down_revision: str | None = "0012_cold_email_drafts"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cold_email_drafts", sa.Column("recipient_email", sa.String(length=320), nullable=True))
    op.add_column("cold_email_drafts", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cold_email_drafts", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cold_email_drafts", sa.Column("last_error", sa.Text(), nullable=True))



def downgrade() -> None:
    op.drop_column("cold_email_drafts", "last_error")
    op.drop_column("cold_email_drafts", "sent_at")
    op.drop_column("cold_email_drafts", "approved_at")
    op.drop_column("cold_email_drafts", "recipient_email")
