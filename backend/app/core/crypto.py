"""Symmetric encryption for sensitive values stored at rest — currently
connected Gmail OAuth tokens (EmailAccount.access_token/refresh_token), keyed
by settings.email_token_encryption_key.

Falls back to returning the raw value on read when it isn't a valid Fernet
token, so rows written before this was wired in (or written while the key is
unset) keep working without a data migration — every value written *while a
key is configured* is always encrypted going forward.
"""
import logging
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _fernet() -> Optional[Fernet]:
    key = (settings.email_token_encryption_key or "").strip()
    if not key:
        logger.warning(
            "EMAIL_TOKEN_ENCRYPTION_KEY is not set — connected account tokens "
            "(e.g. Gmail OAuth) are being stored in plaintext. Generate a key with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
        return None
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        # A configured-but-invalid key is a deployment mistake, not a normal
        # "encryption is off" state — fail loudly instead of silently storing
        # plaintext under a false sense of security.
        raise RuntimeError(
            "EMAIL_TOKEN_ENCRYPTION_KEY is set but is not a valid Fernet key "
            "(must be 32 url-safe base64-encoded bytes)."
        ) from exc


def encrypt_token(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    fernet = _fernet()
    if fernet is None:
        return value
    return fernet.encrypt(value.encode()).decode()


def decrypt_token(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    fernet = _fernet()
    if fernet is None:
        return value
    try:
        return fernet.decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        # Stored before encryption was enabled, or under a different key —
        # return as-is rather than breaking a previously-connected account.
        return value
