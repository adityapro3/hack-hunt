import logging

from cryptography.fernet import Fernet, InvalidToken

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

_ENCRYPTION_PREFIX = "enc:v1:"


def _get_fernet() -> Fernet:
    key = (get_settings().api_key_encryption_key or "").strip()
    if not key:
        raise RuntimeError(
            "API key encryption is not configured. Set API_KEY_ENCRYPTION_KEY in environment."
        )

    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive path
        raise RuntimeError(
            "Invalid API_KEY_ENCRYPTION_KEY format. Use a valid Fernet key."
        ) from exc


def is_encrypted_secret(value: str | None) -> bool:
    return bool(value and value.startswith(_ENCRYPTION_PREFIX))


def encrypt_secret_value(value: str | None) -> str | None:
    if value is None:
        return None

    raw = value.strip()
    if not raw:
        return None

    if is_encrypted_secret(raw):
        return raw

    fernet = _get_fernet()
    token = fernet.encrypt(raw.encode("utf-8")).decode("utf-8")
    return f"{_ENCRYPTION_PREFIX}{token}"


def decrypt_secret_value(value: str | None) -> str | None:
    if value is None:
        return None

    raw = value.strip()
    if not raw:
        return None

    if not is_encrypted_secret(raw):
        # Backward compatibility for legacy plaintext rows.
        return raw

    token = raw[len(_ENCRYPTION_PREFIX) :]
    fernet = _get_fernet()

    try:
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored secret cannot be decrypted with current key") from exc
