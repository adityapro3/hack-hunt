"""Encrypt API keys in user_settings and migrate plaintext values.

Revision ID: 0011_encrypt_api_keys
Revises: 0010_drop_ollama_cloud_url
Create Date: 2026-04-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0011_encrypt_api_keys"
down_revision: str | None = "0010_drop_ollama_cloud_url"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("gemini_api_key_enc", sa.Text(), nullable=True))
    op.add_column("user_settings", sa.Column("openai_api_key_enc", sa.Text(), nullable=True))
    op.add_column("user_settings", sa.Column("anthropic_api_key_enc", sa.Text(), nullable=True))
    op.add_column("user_settings", sa.Column("ollama_cloud_api_key_enc", sa.Text(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, gemini_api_key, openai_api_key, anthropic_api_key, ollama_cloud_api_key
            FROM user_settings
            """
        )
    ).mappings().all()

    if rows:
        from backend.services.common.secrets import encrypt_secret_value

        for row in rows:
            bind.execute(
                sa.text(
                    """
                    UPDATE user_settings
                    SET
                      gemini_api_key_enc = :gemini_api_key_enc,
                      openai_api_key_enc = :openai_api_key_enc,
                      anthropic_api_key_enc = :anthropic_api_key_enc,
                      ollama_cloud_api_key_enc = :ollama_cloud_api_key_enc
                    WHERE id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "gemini_api_key_enc": encrypt_secret_value(row.get("gemini_api_key")),
                    "openai_api_key_enc": encrypt_secret_value(row.get("openai_api_key")),
                    "anthropic_api_key_enc": encrypt_secret_value(row.get("anthropic_api_key")),
                    "ollama_cloud_api_key_enc": encrypt_secret_value(row.get("ollama_cloud_api_key")),
                },
            )

    op.drop_column("user_settings", "gemini_api_key")
    op.drop_column("user_settings", "openai_api_key")
    op.drop_column("user_settings", "anthropic_api_key")
    op.drop_column("user_settings", "ollama_cloud_api_key")

    op.alter_column("user_settings", "gemini_api_key_enc", new_column_name="gemini_api_key")
    op.alter_column("user_settings", "openai_api_key_enc", new_column_name="openai_api_key")
    op.alter_column("user_settings", "anthropic_api_key_enc", new_column_name="anthropic_api_key")
    op.alter_column("user_settings", "ollama_cloud_api_key_enc", new_column_name="ollama_cloud_api_key")


def downgrade() -> None:
    op.add_column("user_settings", sa.Column("gemini_api_key_plain", sa.String(length=500), nullable=True))
    op.add_column("user_settings", sa.Column("openai_api_key_plain", sa.String(length=500), nullable=True))
    op.add_column("user_settings", sa.Column("anthropic_api_key_plain", sa.String(length=500), nullable=True))
    op.add_column("user_settings", sa.Column("ollama_cloud_api_key_plain", sa.String(length=500), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, gemini_api_key, openai_api_key, anthropic_api_key, ollama_cloud_api_key
            FROM user_settings
            """
        )
    ).mappings().all()

    if rows:
        from backend.services.common.secrets import decrypt_secret_value

        for row in rows:
            bind.execute(
                sa.text(
                    """
                    UPDATE user_settings
                    SET
                      gemini_api_key_plain = :gemini_api_key_plain,
                      openai_api_key_plain = :openai_api_key_plain,
                      anthropic_api_key_plain = :anthropic_api_key_plain,
                      ollama_cloud_api_key_plain = :ollama_cloud_api_key_plain
                    WHERE id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "gemini_api_key_plain": decrypt_secret_value(row.get("gemini_api_key")),
                    "openai_api_key_plain": decrypt_secret_value(row.get("openai_api_key")),
                    "anthropic_api_key_plain": decrypt_secret_value(row.get("anthropic_api_key")),
                    "ollama_cloud_api_key_plain": decrypt_secret_value(row.get("ollama_cloud_api_key")),
                },
            )

    op.drop_column("user_settings", "gemini_api_key")
    op.drop_column("user_settings", "openai_api_key")
    op.drop_column("user_settings", "anthropic_api_key")
    op.drop_column("user_settings", "ollama_cloud_api_key")

    op.alter_column("user_settings", "gemini_api_key_plain", new_column_name="gemini_api_key")
    op.alter_column("user_settings", "openai_api_key_plain", new_column_name="openai_api_key")
    op.alter_column("user_settings", "anthropic_api_key_plain", new_column_name="anthropic_api_key")
    op.alter_column("user_settings", "ollama_cloud_api_key_plain", new_column_name="ollama_cloud_api_key")
