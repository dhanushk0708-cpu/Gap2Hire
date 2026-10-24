from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": user_id,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> str:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[ALGORITHM],
    )

    return payload["sub"]


def _get_encryption_key() -> bytes:
    import base64
    import hashlib

    key = getattr(settings, "token_encryption_key", "")
    if key:
        try:
            raw = key.encode("utf-8") if isinstance(key, str) else key
            # Check if valid 32-byte urlsafe base64 key
            decoded = base64.urlsafe_b64decode(raw)
            if len(decoded) == 32:
                return raw
        except Exception:
            pass
        derived = hashlib.sha256(key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(derived)

    # Deterministically derive 32-byte urlsafe base64 key from jwt_secret_key
    derived = hashlib.sha256(settings.jwt_secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(derived)


def encrypt_auth_payload(payload: dict) -> str:
    """Encrypts sensitive OAuth credential payload using Fernet (AES-128-CBC + HMAC)."""
    import json
    from cryptography.fernet import Fernet

    key = _get_encryption_key()
    fernet = Fernet(key)
    raw = json.dumps(payload).encode("utf-8")
    return fernet.encrypt(raw).decode("utf-8")


def decrypt_auth_payload(encrypted_text: str | None) -> dict:
    """Decrypts sensitive OAuth credential payload, handling legacy plain JSON transparently."""
    if not encrypted_text:
        return {}

    import json
    import logging
    from cryptography.fernet import Fernet

    trimmed = encrypted_text.strip()
    # Backwards compatibility check for legacy unencrypted JSON
    if trimmed.startswith("{") and trimmed.endswith("}"):
        try:
            return json.loads(trimmed)
        except Exception:
            pass

    try:
        key = _get_encryption_key()
        fernet = Fernet(key)
        decrypted = fernet.decrypt(trimmed.encode("utf-8"))
        return json.loads(decrypted.decode("utf-8"))
    except Exception as exc:
        logger = logging.getLogger(__name__)
        logger.error("Failed to decrypt OAuth credentials payload. Key mismatch or data corrupted.")
        raise ValueError("Could not decrypt token payload. Invalid encryption key or corrupted data.") from exc


def generate_oauth_state(organization_id, user_id=None) -> str:
    """Generates a cryptographically signed, tenant-bound OAuth state parameter to prevent CSRF."""
    import secrets
    import time

    payload = {
        "org_id": str(organization_id),
        "user_id": str(user_id) if user_id else None,
        "nonce": secrets.token_hex(16),
        "exp": int(time.time()) + 900,  # 15 minutes validity
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def validate_oauth_state(state: str) -> dict:
    """Validates the OAuth state parameter signature, expiry, and organization claim."""
    if not state:
        raise ValueError("Missing OAuth state parameter. Request rejected for CSRF protection.")

    try:
        payload = jwt.decode(state, settings.jwt_secret_key, algorithms=[ALGORITHM])
        if "org_id" not in payload:
            raise ValueError("OAuth state token missing organization identifier.")
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("OAuth state parameter has expired. Please initiate authentication again.")
    except Exception as exc:
        raise ValueError(f"Invalid OAuth state parameter: {exc}")