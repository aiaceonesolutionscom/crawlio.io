from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core import login_rate_limit
from app.core.config import settings

router = APIRouter()


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    token: str
    username: str


@router.post("/auth/login", response_model=AdminLoginResponse)
async def admin_login(body: AdminLoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    # Keyed by IP+username so one bad actor can't lock out the real admin,
    # and one IP can't grind through many usernames unthrottled either.
    rate_key = f"{client_ip}:{body.username}"
    locked, retry_after = login_rate_limit.is_locked_out(rate_key)
    if locked:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {int(retry_after)}s.",
        )

    if body.username != settings.admin_username or body.password != settings.admin_password:
        login_rate_limit.record_failure(rate_key)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    login_rate_limit.record_success(rate_key)
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.admin_jwt_expire_hours)
    token = jwt.encode(
        {"sub": body.username, "exp": expire, "type": "admin_panel"},
        settings.admin_jwt_secret,
        algorithm="HS256",
    )
    return AdminLoginResponse(token=token, username=body.username)
