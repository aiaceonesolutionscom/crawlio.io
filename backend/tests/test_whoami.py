import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core import security
from app.core.config import settings

TEST_ISSUER = "https://fit-badger-93.clerk.accounts.dev"


def _make_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


async def test_whoami_requires_bearer_token(client):
    resp = await client.get("/api/v1/_whoami")
    assert resp.status_code == 401


async def test_whoami_returns_sub_for_valid_token(client, monkeypatch):
    monkeypatch.setattr(settings, "clerk_issuer", TEST_ISSUER)
    private_key, public_key = _make_keypair()

    class FakeSigningKey:
        key = public_key

    class FakeJWKClient:
        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey()

    monkeypatch.setattr(security, "_get_jwk_client", lambda: FakeJWKClient())

    now = int(time.time())
    token = jwt.encode(
        {"sub": "user_abc123", "iss": TEST_ISSUER, "iat": now, "exp": now + 3600},
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"}
    )

    resp = await client.get("/api/v1/_whoami", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"user_id": "user_abc123"}
