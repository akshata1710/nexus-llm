import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from core.config import settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(subject: str, extra: dict | None = None) -> str:
    payload = {
        "sub": subject,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    payload = {
        "sub": subject,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])


def generate_api_key() -> tuple[str, str, str]:
    raw = secrets.token_urlsafe(32)
    full_key = f"{settings.api_key_prefix}-{raw}"
    key_prefix = f"{settings.api_key_prefix}-{raw[:8]}"
    key_hash = _hash_api_key(full_key)
    return full_key, key_prefix, key_hash


def hash_api_key(full_key: str) -> str:
    return _hash_api_key(full_key)


def _hash_api_key(key: str) -> str:
    return hmac.new(
        settings.secret_key.encode(),
        key.encode(),
        hashlib.sha256,
    ).hexdigest()