from fastapi import APIRouter, Depends

from app.api.v1 import analytics, automation, discovery, geo, leads, team, webhooks, workspaces
from app.core.deps import get_current_user_id

api_router = APIRouter()
api_router.include_router(workspaces.router)
api_router.include_router(leads.router)
api_router.include_router(discovery.router)
api_router.include_router(geo.router)
api_router.include_router(automation.router)
api_router.include_router(webhooks.router)
api_router.include_router(analytics.router)
api_router.include_router(team.router)


@api_router.get("/_whoami")
async def whoami(user_id: str = Depends(get_current_user_id)):
    """Debug endpoint proving Clerk JWT verification works end to end."""
    return {"user_id": user_id}
