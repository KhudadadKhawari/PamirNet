import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _key() -> bytes:
    configured = getattr(settings, "PAMIRNET_ENCRYPTION_KEY", "").strip()
    if configured:
        try:
            raw = base64.urlsafe_b64decode(configured.encode())
        except Exception as exc:  # pragma: no cover - defensive config validation
            raise ValueError(
                "PAMIRNET_ENCRYPTION_KEY must be a Fernet-compatible base64 key."
            ) from exc
        if len(raw) != 32:
            raise ValueError("PAMIRNET_ENCRYPTION_KEY must decode to exactly 32 bytes.")
        return configured.encode()

    # Development fallback only. Production deployments must set PAMIRNET_ENCRYPTION_KEY.
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return Fernet(_key()).encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        return Fernet(_key()).decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Unable to decrypt stored secret with the configured PamirNet key."
        ) from exc
