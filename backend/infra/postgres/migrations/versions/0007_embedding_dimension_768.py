"""Increase opportunity embedding dimension to 768.

Revision ID: 0007_embedding_dimension_768
Revises: 0006_chat_threads_and_messages
Create Date: 2026-04-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_embedding_dimension_768"
down_revision: str | None = "0006_chat_threads_and_messages"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Existing rows may contain 384-d vectors; clear them before type change.
    # Rebuild embeddings after migration to avoid truncation.
    op.execute("DROP INDEX IF EXISTS idx_opportunities_embedding")
    op.execute("UPDATE opportunities SET embedding = NULL WHERE embedding IS NOT NULL")
    op.execute("ALTER TABLE opportunities ALTER COLUMN embedding TYPE vector(768)")
    op.execute(
        "CREATE INDEX idx_opportunities_embedding ON opportunities USING ivfflat (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_opportunities_embedding")
    op.execute("UPDATE opportunities SET embedding = NULL WHERE embedding IS NOT NULL")
    op.execute("ALTER TABLE opportunities ALTER COLUMN embedding TYPE vector(384)")
    op.execute(
        "CREATE INDEX idx_opportunities_embedding ON opportunities USING ivfflat (embedding vector_cosine_ops)"
    )
