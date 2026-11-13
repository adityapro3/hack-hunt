"""Switch default embedding model from MiniLM to Nomic.

Revision ID: 0014_embed_model_nomic
Revises: 0013_cold_email_delivery_fields
Create Date: 2026-04-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014_embed_model_nomic"
down_revision: str | None = "0013_cold_email_delivery_fields"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE app_config ALTER COLUMN embedding_model SET DEFAULT 'nomic-ai/nomic-embed-text-v1.5'"
    )
    op.execute(
        """
        UPDATE app_config
        SET embedding_model = 'nomic-ai/nomic-embed-text-v1.5'
        WHERE lower(embedding_provider) = 'huggingface'
          AND embedding_model IN ('all-MiniLM-L6-v2', 'sentence-transformers/all-MiniLM-L6-v2')
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE app_config ALTER COLUMN embedding_model SET DEFAULT 'sentence-transformers/all-MiniLM-L6-v2'"
    )
    op.execute(
        """
        UPDATE app_config
        SET embedding_model = 'sentence-transformers/all-MiniLM-L6-v2'
        WHERE lower(embedding_provider) = 'huggingface'
          AND embedding_model = 'nomic-ai/nomic-embed-text-v1.5'
        """
    )