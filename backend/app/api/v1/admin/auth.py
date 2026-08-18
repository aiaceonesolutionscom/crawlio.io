from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    token: str
    username: str


@router.post("/auth/login", response_model=AdminLoginResponse)
async def admin_login(body: AdminLoginRequest):
    if body.username != settings.admin_username or body.password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    expire = datetime.now(timezone.utc) + timedelta(hours=settings.admin_jwt_expire_hours)
    token = jwt.encode(
        {"sub": body.username, "exp": expire, "type": "admin_panel"},
        settings.admin_jwt_secret,
        algorithm="HS256",
    )
    return AdminLoginResponse(token=token, username=body.username)
