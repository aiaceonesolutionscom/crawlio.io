from typing import Annotated, Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_clerk_jwt
from app.db.models.platform_admin import PlatformAdmin
from app.db.session import get_session
from app.services.platform_admin_service import resolve_or_bootstrap

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_claims(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)]
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return verify_clerk_jwt(credentials.credentials)


async def require_super_admin(
    claims: Annotated[dict[str, Any], Depends(get_current_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PlatformAdmin:
    admin = await resolve_or_bootstrap(session, claims)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")
    return admin
