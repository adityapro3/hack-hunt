from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps.auth import get_current_user
from backend.infra.postgres.session import get_db
from backend.infra.postgres.tables import User, UserSettings
from backend.schemas import SavedModelUpdateRequest, UserSettingsResponse, UserSettingsUpdateRequest
from backend.services.common import encrypt_secret_value
from backend.services.users.settings import get_or_create_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])
_SUPPORTED_PROVIDERS = ("gemini", "openai", "anthropic", "ollama", "ollama_cloud")


def _normalize_saved_models(raw: dict | None) -> dict[str, list[str]]:
    data = raw or {}
    normalized: dict[str, list[str]] = {provider: [] for provider in _SUPPORTED_PROVIDERS}
    for provider in _SUPPORTED_PROVIDERS:
        values = data.get(provider)
        if not isinstance(values, list):
            continue
        deduped: list[str] = []
        seen: set[str] = set()
        for item in values:
            if not isinstance(item, str):
                continue
            value = item.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        normalized[provider] = deduped
    return normalized


def _to_settings_response(row: UserSettings) -> UserSettingsResponse:
    return UserSettingsResponse(
        id=row.id,
        has_gemini_key=bool(row.gemini_api_key),
        has_openai_key=bool(row.openai_api_key),
        has_anthropic_key=bool(row.anthropic_api_key),
        has_ollama_cloud_key=bool(row.ollama_cloud_api_key),
        ollama_model=row.ollama_model,
        ollama_base_url=row.ollama_base_url,
        saved_models=_normalize_saved_models(row.saved_models),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=UserSettingsResponse)
def get_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = get_or_create_settings(db, current_user.id)
    return _to_settings_response(row)


@router.put("", response_model=UserSettingsResponse)
def update_settings(
    payload: UserSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_or_create_settings(db, current_user.id)

    updates = payload.model_dump(exclude_unset=True)
    secret_fields = (
        "gemini_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "ollama_cloud_api_key",
    )
    for secret_field in secret_fields:
        if secret_field in updates:
            updates[secret_field] = encrypt_secret_value(updates[secret_field])

    for key, value in updates.items():
        setattr(row, key, value)

    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_settings_response(row)


@router.post("/models", response_model=UserSettingsResponse)
def add_saved_model(
    payload: SavedModelUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model_name = payload.model.strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="model is required")

    row = get_or_create_settings(db, current_user.id)
    saved = _normalize_saved_models(row.saved_models)
    if model_name not in saved[payload.provider]:
        saved[payload.provider].append(model_name)

    row.saved_models = saved
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_settings_response(row)


@router.delete("/models", response_model=UserSettingsResponse)
def remove_saved_model(
    provider: str,
    model: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    provider_key = provider.strip().lower()
    if provider_key not in _SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail="provider must be one of gemini, openai, anthropic, ollama, ollama_cloud",
        )

    model_name = model.strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="model is required")

    row = get_or_create_settings(db, current_user.id)
    saved = _normalize_saved_models(row.saved_models)
    saved[provider_key] = [item for item in saved[provider_key] if item != model_name]

    row.saved_models = saved
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_settings_response(row)
