from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import PLAN_LIMITS
from app.db.models.invitation import Invitation
from app.db.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import WorkspaceCreate
from app.workers.tasks_email import send_welcome_email_task


async def get_workspace_for_user(session: AsyncSession, user_id: str) -> Optional[Workspace]:
    result = await session.execute(
        select(Workspace).join(WorkspaceMember).where(WorkspaceMember.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def _accept_pending_invitation(
    session: AsyncSession, user_id: str, data: WorkspaceCreate
) -> Optional[Workspace]:
    if not data.owner_email:
        return None

    result = await session.execute(
        select(Invitation).where(Invitation.email == data.owner_email, Invitation.status == "pending")
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        return None

    member = WorkspaceMember(
        workspace_id=invitation.workspace_id,
        user_id=user_id,
        email=data.owner_email,
        name=data.owner_name,
        role=invitation.role
    )
    session.add(member)
    invitation.status = "accepted"
    await session.commit()

    result = await session.execute(select(Workspace).where(Workspace.id == invitation.workspace_id))
    return result.scalar_one()


async def create_workspace(session: AsyncSession, user_id: str, data: WorkspaceCreate) -> Workspace:
    """Idempotent: a second call for the same user returns their existing workspace
    rather than erroring, since the frontend calls this opportunistically on first
    /app visit regardless of whether it's a fresh signup or a returning login.

    If a pending team invitation matches the signed-in user's email, they join
    that workspace instead of getting a brand-new one — this is what actually
    fulfils an invite sent from Team settings, since there's no separate
    accept-invite flow in the frontend.

    Plan is always 'free' for brand-new workspaces regardless of client input —
    upgrades only happen through the explicit PATCH /workspaces/{id}/plan endpoint.
    """
    existing = await get_workspace_for_user(session, user_id)
    if existing is not None:
        return existing

    joined = await _accept_pending_invitation(session, user_id, data)
    if joined is not None:
        return joined

    limits = PLAN_LIMITS["free"]
    workspace = Workspace(name=data.name, plan="free", lead_quota=limits["leads"], seat_quota=limits["seats"])
    session.add(workspace)
    await session.flush()

    member = WorkspaceMember(
        workspace_id=workspace.id, user_id=user_id, email=data.owner_email, name=data.owner_name, role="Owner"
    )
    session.add(member)
    await session.commit()
    await session.refresh(workspace)

    if data.owner_email:
        send_welcome_email_task.delay(data.owner_email, data.owner_name or "there", workspace.name)

    return workspace


async def change_plan(session: AsyncSession, workspace: Workspace, new_plan: str) -> Workspace:
    limits = PLAN_LIMITS[new_plan]
    workspace.plan = new_plan
    workspace.lead_quota = limits["leads"]
    workspace.seat_quota = limits["seats"]
    await session.commit()
    await session.refresh(workspace)
    return workspace
