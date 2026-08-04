from fastapi import APIRouter, Depends

from app.core.deps import get_current_user_id

api_router = APIRouter()

# Domain routers (workspaces, leads, automation, analytics, team, webhooks)
# are registered here as they land in later phases.


@api_router.get("/_whoami")
async def whoami(user_id: str = Depends(get_current_user_id)):
    """Debug endpoint proving Clerk JWT verification works end to end."""
    return {"user_id": user_id}
