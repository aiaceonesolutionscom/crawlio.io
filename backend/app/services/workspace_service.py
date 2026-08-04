from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import PLAN_LIMITS
from app.db.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import WorkspaceCreate


async def get_workspace_for_user(session: AsyncSession, user_id: str) -> Optional[Workspace]:
    result = await session.execute(
        select(Workspace).join(WorkspaceMember).where(WorkspaceMember.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_workspace(session: AsyncSession, user_id: str, data: WorkspaceCreate) -> Workspace:
    """Idempotent: a second call for the same user returns their existing workspace
    rather than erroring, since the frontend calls this opportunistically on first
    /app visit regardless of whether it's a fresh signup or a returning login.

    Plan is always 'free' here regardless of client input — upgrades only happen
    through the explicit PATCH /workspaces/{id}/plan endpoint, never at creation.
    """
    existing = await get_workspace_for_user(session, user_id)
    if existing is not None:
        return existing

    limits = PLAN_LIMITS["free"]
    workspace = Workspace(name=data.name, plan="free", lead_quota=limits["leads"], seat_quota=limits["seats"])
    session.add(workspace)
    await session.flush()

    member = WorkspaceMember(workspace_id=workspace.id, user_id=user_id, role="Owner")
    session.add(member)
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def change_plan(session: AsyncSession, workspace: Workspace, new_plan: str) -> Workspace:
    limits = PLAN_LIMITS[new_plan]
    workspace.plan = new_plan
    workspace.lead_quota = limits["leads"]
    workspace.seat_quota = limits["seats"]
    await session.commit()
    await session.refresh(workspace)
    return workspace
