from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.email import EmailMessage
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.automation import InboundLeadCapture
from app.schemas.lead import LeadCreate
from app.services import lead_service
from app.workers.tasks_scoring import score_lead_task

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/leads/{workspace_id}", status_code=status.HTTP_201_CREATED)
async def capture_inbound_lead(
    workspace_id: str,
    payload: InboundLeadCapture,
    session: Annotated[AsyncSession, Depends(get_session)],
    token: str = Query(...)
):
    """Public endpoint for external forms/integrations to push a lead into a
    workspace. Auth is the workspace's own webhook_token (query param), not a
    Clerk session — the caller is a server or form handler, not a logged-in user."""
    result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None or workspace.webhook_token != token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown workspace or webhook token")

    lead = await lead_service.create_lead(
        session,
        workspace,
        LeadCreate(
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            source=payload.source
        )
    )
    score_lead_task.delay(lead.id)
    return {"id": lead.id, "status": "captured"}


_BREVO_STATUS_BY_EVENT = {
    "delivered": "delivered",
    "hard_bounce": "bounced",
    "soft_bounce": "bounced",
    "blocked": "blocked",
    "spam": "complained",
    "deferred": "delayed",
    "error": "failed"
}


@router.post("/brevo")
async def brevo_event_webhook(payload: dict[str, Any], session: Annotated[AsyncSession, Depends(get_session)]):
    """Receives Brevo transactional-email delivery-status events and updates the
    matching EmailMessage row. Brevo webhooks aren't signed by default; signature
    verification is left for production hardening once one is configured."""
    event_type = payload.get("event", "")
    new_status = _BREVO_STATUS_BY_EVENT.get(event_type)
    provider_message_id = payload.get("message-id")
    if new_status is None or not provider_message_id:
        return {"received": True, "applied": False}

    result = await session.execute(
        select(EmailMessage).where(EmailMessage.provider_message_id == provider_message_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        return {"received": True, "applied": False}

    message.status = new_status
    if new_status == "delivered":
        message.sent_at = datetime.now(timezone.utc)
    await session.commit()
    return {"received": True, "applied": True}
