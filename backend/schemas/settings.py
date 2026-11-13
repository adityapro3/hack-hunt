from datetime import datetime
from typing import Literal

from pydantic import BaseModel


ChatProviderName = Literal["gemini", "openai", "anthropic", "ollama", "ollama_cloud"]


class UserSettingsUpdateRequest(BaseModel):
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    ollama_model: str | None = None
    ollama_base_url: str | None = None
    ollama_cloud_api_key: str | None = None


class UserSettingsResponse(BaseModel):
    id: int
    has_gemini_key: bool
    has_openai_key: bool
    has_anthropic_key: bool
    has_ollama_cloud_key: bool
    ollama_model: str
    ollama_base_url: str
    saved_models: dict[ChatProviderName, list[str]]
    created_at: datetime
    updated_at: datetime


class SavedModelUpdateRequest(BaseModel):
    provider: ChatProviderName
    model: str
