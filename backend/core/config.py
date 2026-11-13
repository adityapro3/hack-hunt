from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/hack_hunt"
    supabase_db_url: str | None = None
    database_sslmode: str | None = None
    embedding_model_name: str = "nomic-ai/nomic-embed-text-v1.5"
    embedding_ollama_model: str = "nomic-embed-text:v1.5"
    embedding_ollama_base_url: str = "http://localhost:11434"
    embedding_vector_dimension: int = 768
    news_topic_model_dir: str | None = None
    news_topic_default_label: str = "general"
    chat_context_limit: int = 20
    coldemail_max_professors_per_run: int = 50
    coldemail_rate_limit_per_day: int = 50
    coldemail_profile_base_url: str = "https://ollama.com/v1"
    coldemail_profile_model: str = "gemma4:31b-cloud"
    coldemail_profile_api_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    api_key_encryption_key: str | None = None
    jwt_secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24
    admin_signup_key: str | None = None
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8501"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_database_url(self) -> str:
        return self.supabase_db_url or self.database_url

    @property
    def database_connect_args(self) -> dict[str, object]:
        url = self.resolved_database_url
        args: dict[str, object] = {}

        if "pooler.supabase.com" in url:
            args["prepare_threshold"] = None

        if "sslmode=" in url:
            return args

        sslmode = self.database_sslmode
        if not sslmode and self.supabase_db_url:
            sslmode = "require"

        if sslmode:
            args["sslmode"] = sslmode

        return args

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
