from fastapi import APIRouter, Depends

from app.api.v1 import analytics, automation, crm, discovery, email_accounts, email_agent, email_ai, email_conversations, email_drafts, geo, leads, team, webhooks, workspaces
from app.api.v1.admin import admin_router
from app.core.deps import get_current_user_id

api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(workspaces.router)
api_router.include_router(leads.router)
api_router.include_router(discovery.router)
api_router.include_router(geo.router)
api_router.include_router(crm.router)
api_router.include_router(automation.router)
api_router.include_router(email_accounts.router)
api_router.include_router(email_drafts.router)
api_router.include_router(email_ai.router)
api_router.include_router(email_agent.router)
api_router.include_router(email_conversations.router)
api_router.include_router(webhooks.router)
api_router.include_router(analytics.router)
api_router.include_router(team.router)


@api_router.get("/_whoami")
async def whoami(user_id: str = Depends(get_current_user_id)):
    """Debug endpoint proving Clerk JWT verification works end to end."""
    return {"user_id": user_id}
