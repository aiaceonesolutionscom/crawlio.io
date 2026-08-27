from app.core import login_rate_limit
from app.core.config import settings


async def test_correct_credentials_return_token(client):
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert resp.status_code == 200
    assert resp.json()["token"]


async def test_wrong_password_returns_401(client):
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": settings.admin_username, "password": "definitely-wrong"},
    )
    assert resp.status_code == 401


async def test_repeated_failures_lock_out_the_ip_username_pair(client):
    login_rate_limit._failures.clear()
    for _ in range(login_rate_limit.MAX_ATTEMPTS):
        resp = await client.post(
            "/api/v1/admin/auth/login",
            json={"username": settings.admin_username, "password": "wrong"},
        )
        assert resp.status_code == 401

    locked_resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": settings.admin_username, "password": "wrong"},
    )
    assert locked_resp.status_code == 429

    # Even the *correct* password is refused while locked out — that's the point.
    still_locked = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert still_locked.status_code == 429
    login_rate_limit._failures.clear()


async def test_lockout_is_scoped_per_username_not_global(client):
    login_rate_limit._failures.clear()
    for _ in range(login_rate_limit.MAX_ATTEMPTS):
        await client.post(
            "/api/v1/admin/auth/login",
            json={"username": "attacker", "password": "wrong"},
        )

    # A different username from the same client isn't caught by that lockout.
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert resp.status_code == 200
    login_rate_limit._failures.clear()


async def test_successful_login_clears_prior_failures(client):
    login_rate_limit._failures.clear()
    for _ in range(login_rate_limit.MAX_ATTEMPTS - 1):
        await client.post(
            "/api/v1/admin/auth/login",
            json={"username": settings.admin_username, "password": "wrong"},
        )

    good = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert good.status_code == 200

    # One more good login right after — must not be blocked by the near-miss streak.
    good_again = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert good_again.status_code == 200
    login_rate_limit._failures.clear()
