from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.invitation import Invitation
from app.db.models.lead import Lead
from app.db.models.workspace import Workspace, WorkspaceMember


async def count_leads(session: AsyncSession, workspace_id: str) -> int:
    result = await session.execute(select(func.count()).select_from(Lead).where(Lead.workspace_id == workspace_id))
    return result.scalar_one()


async def count_discovery_leads_today(session: AsyncSession, workspace_id: str) -> int:
    """How many leads this workspace has imported via Lead Discovery since
    midnight UTC today — the daily cap is separate from (and usually much
    smaller than) the overall lead_quota."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(func.count())
        .select_from(Lead)
        .where(
            Lead.workspace_id == workspace_id,
            Lead.source.like("Lead Discovery%"),
            Lead.created_at >= today_start,
        )
    )
    return result.scalar_one()


async def count_seats(session: AsyncSession, workspace_id: str) -> int:
    """Active members plus still-pending invites, since a pending invite reserves a seat."""
    members_result = await session.execute(
        select(func.count()).select_from(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
    )
    invites_result = await session.execute(
        select(func.count())
        .select_from(Invitation)
        .where(Invitation.workspace_id == workspace_id, Invitation.status == "pending")
    )
    return members_result.scalar_one() + invites_result.scalar_one()


async def check_lead_quota(session: AsyncSession, workspace: Workspace) -> None:
    count = await count_leads(session, workspace.id)
    if count >= workspace.lead_quota:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Lead quota reached ({workspace.lead_quota} for the {workspace.plan} plan). "
                "Upgrade to add more leads."
            )
        )


async def check_seat_quota(session: AsyncSession, workspace: Workspace) -> None:
    count = await count_seats(session, workspace.id)
    if count >= workspace.seat_quota:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Seat quota reached ({workspace.seat_quota} for the {workspace.plan} plan). "
                "Upgrade to invite more teammates."
            )
        )
