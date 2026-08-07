from typing import Any, Optional

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from app.core.config import settings

_jwk_client: Optional[PyJWKClient] = None


def _get_jwk_client() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        if not settings.clerk_jwks_url:
            raise RuntimeError("CLERK_JWKS_URL is not configured")
        _jwk_client = PyJWKClient(settings.clerk_jwks_url, cache_keys=True)
    return _jwk_client


def verify_clerk_jwt(token: str) -> dict[str, Any]:
    """Verifies a Clerk session JWT against Clerk's JWKS and returns its claims.

    Signature, issuer, and expiry are all checked. Clerk's default session
    tokens don't carry an audience claim, so `aud` isn't verified here.
    """
    try:
        signing_key = _get_jwk_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            options={"require": ["exp", "iat", "sub"]},
            # Clerk issues the token against its own clock, which is never
            # perfectly in sync with this server's — without leeway, a token
            # can be rejected as "not yet valid" (iat in the future) purely
            # from a couple seconds of clock drift, well before it's actually
            # anywhere near expiry.
            leeway=60,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {exc}",
        ) from exc
    return claims
