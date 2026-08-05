from fastapi import APIRouter, Depends

from app.api.v1 import automation, leads, webhooks, workspaces
from app.core.deps import get_current_user_id

api_router = APIRouter()
api_router.include_router(workspaces.router)
api_router.include_router(leads.router)
api_router.include_router(automation.router)
api_router.include_router(webhooks.router)

# Domain routers (analytics, team) are registered here as they land in later phases.


@api_router.get("/_whoami")
async def whoami(user_id: str = Depends(get_current_user_id)):
    """Debug endpoint proving Clerk JWT verification works end to end."""
    return {"user_id": user_id}
