from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import PLAN_CAPABILITIES
from app.core.security import verify_clerk_jwt
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.services.workspace_service import get_workspace_for_user

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)]
) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    claims = verify_clerk_jwt(credentials.credentials)
    return claims["sub"]


async def get_current_workspace(
    user_id: Annotated[str, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)]
) -> Workspace:
    workspace = await get_workspace_for_user(session, user_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No workspace found for this user")
    return workspace


def require_plan(capability: str):
    def dependency(workspace: Annotated[Workspace, Depends(get_current_workspace)]) -> Workspace:
        if capability not in PLAN_CAPABILITIES.get(workspace.plan, set()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"'{capability}' requires a higher plan"
            )
        return workspace

    return dependency
