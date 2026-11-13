import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from backend.core.config import get_settings


PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 390_000
SALT_BYTES = 16
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != f"pbkdf2_{PBKDF2_ALGORITHM}":
        return False

    try:
        derived = hashlib.pbkdf2_hmac(
            PBKDF2_ALGORITHM,
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
    except ValueError:
        return False

    return hmac.compare_digest(derived.hex(), digest_hex)


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expires_at = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[JWT_ALGORITHM])
    except InvalidTokenError as exc:
        raise ValueError("Invalid token") from exc

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise ValueError("Invalid token subject")

    try:
        return UUID(subject)
    except ValueError as exc:
        raise ValueError("Invalid token subject") from exc
