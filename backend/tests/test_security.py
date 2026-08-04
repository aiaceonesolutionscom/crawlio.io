import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.core import security
from app.core.config import settings

TEST_ISSUER = "https://fit-badger-93.clerk.accounts.dev"


def _make_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _sign(private_key, claims):
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def _patch_jwk_client(monkeypatch, public_key):
    class FakeSigningKey:
        key = public_key

    class FakeJWKClient:
        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey()

    monkeypatch.setattr(security, "_get_jwk_client", lambda: FakeJWKClient())


@pytest.fixture(autouse=True)
def _set_issuer(monkeypatch):
    monkeypatch.setattr(settings, "clerk_issuer", TEST_ISSUER)


def test_verify_clerk_jwt_accepts_valid_token(monkeypatch):
    private_key, public_key = _make_keypair()
    _patch_jwk_client(monkeypatch, public_key)

    now = int(time.time())
    token = _sign(private_key, {"sub": "user_123", "iss": TEST_ISSUER, "iat": now, "exp": now + 3600})

    claims = security.verify_clerk_jwt(token)
    assert claims["sub"] == "user_123"


def test_verify_clerk_jwt_rejects_wrong_signature(monkeypatch):
    private_key, _ = _make_keypair()
    _, other_public_key = _make_keypair()
    _patch_jwk_client(monkeypatch, other_public_key)

    now = int(time.time())
    token = _sign(private_key, {"sub": "user_123", "iss": TEST_ISSUER, "iat": now, "exp": now + 3600})

    with pytest.raises(HTTPException) as exc_info:
        security.verify_clerk_jwt(token)
    assert exc_info.value.status_code == 401


def test_verify_clerk_jwt_rejects_expired_token(monkeypatch):
    private_key, public_key = _make_keypair()
    _patch_jwk_client(monkeypatch, public_key)

    now = int(time.time())
    token = _sign(private_key, {"sub": "user_123", "iss": TEST_ISSUER, "iat": now - 7200, "exp": now - 3600})

    with pytest.raises(HTTPException) as exc_info:
        security.verify_clerk_jwt(token)
    assert exc_info.value.status_code == 401


def test_verify_clerk_jwt_rejects_wrong_issuer(monkeypatch):
    private_key, public_key = _make_keypair()
    _patch_jwk_client(monkeypatch, public_key)

    now = int(time.time())
    token = _sign(
        private_key,
        {"sub": "user_123", "iss": "https://someone-elses-app.clerk.accounts.dev", "iat": now, "exp": now + 3600}
    )

    with pytest.raises(HTTPException) as exc_info:
        security.verify_clerk_jwt(token)
    assert exc_info.value.status_code == 401
