import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.crm import CrmEntry
from app.db.models.email import EmailMessage
from app.db.models.email_account import (
    DailyEmailQuota,
    EmailAccount,
    EmailConversation,
    EmailConversationMessage,
    EmailDraft,
)
from app.db.models.feature_flag import FeatureFlagOverride
from app.db.models.invitation import Invitation
from app.db.models.lead import Lead, LeadEvent
from app.db.models.sequence import Sequence, SequenceStep
from app.db.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import WorkspaceCreate
from app.services import plan_config_service
from app.workers.tasks_email import send_welcome_email_task

logger = logging.getLogger(__name__)


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

    limits = await plan_config_service.get_plan_config_or_404(session, "free")
    workspace = Workspace(
        name=data.name, plan="free", lead_quota=limits.lead_quota, seat_quota=limits.seat_quota
    )
    session.add(workspace)
    await session.flush()

    member = WorkspaceMember(
        workspace_id=workspace.id, user_id=user_id, email=data.owner_email, name=data.owner_name, role="Owner"
    )
    session.add(member)
    await session.commit()
    await session.refresh(workspace)

    if data.owner_email:
        try:
            send_welcome_email_task.delay(data.owner_email, data.owner_name or "there", workspace.name)
        except Exception as exc:
            logger.warning("Could not dispatch welcome email for workspace %s: %s", workspace.id, exc)

    return workspace


async def change_plan(session: AsyncSession, workspace: Workspace, new_plan: str) -> Workspace:
    limits = await plan_config_service.get_plan_config_or_404(session, new_plan)
    workspace.plan = new_plan
    workspace.plan_selected = True
    workspace.lead_quota = limits.lead_quota
    workspace.seat_quota = limits.seat_quota
    await session.commit()
    await session.refresh(workspace)
    return workspace


# --- Admin (platform-wide, cross-tenant) functions below ---


async def list_all_workspaces(
    session: AsyncSession, *, search: Optional[str] = None, limit: int = 50, offset: int = 0
) -> list[Workspace]:
    query = select(Workspace).order_by(Workspace.created_at.desc())
    if search:
        query = query.where(Workspace.name.ilike(f"%{search}%"))
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_workspace_by_id(session: AsyncSession, workspace_id: str) -> Workspace:
    result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace


async def admin_update_workspace(
    session: AsyncSession,
    workspace: Workspace,
    *,
    name: Optional[str] = None,
    plan: Optional[str] = None,
    lead_quota: Optional[int] = None,
    seat_quota: Optional[int] = None,
) -> Workspace:
    """Unlike change_plan(), this lets an admin set a plan alongside custom
    quota overrides in one call, rather than always re-applying the plan's
    defaults — needed for one-off exceptions (e.g. a customer promised extra
    leads without a full plan upgrade)."""
    if plan is not None:
        await plan_config_service.get_plan_config_or_404(session, plan)
        workspace.plan = plan
    if name is not None:
        workspace.name = name
    if lead_quota is not None:
        workspace.lead_quota = lead_quota
    if seat_quota is not None:
        workspace.seat_quota = seat_quota
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def delete_workspace(session: AsyncSession, workspace: Workspace) -> None:
    """Deletes a workspace and every row scoped to it. No cross-table cascade
    exists in the schema beyond Workspace->members, so each tenant-scoped
    table is cleared explicitly, in an order that respects FKs, before the
    workspace row itself (which cascades to WorkspaceMember) is removed.
    """
    workspace_id = workspace.id
    # EmailAccount cascades to its conversations (which cascade to messages)
    # and drafts at the ORM level, but that cascade only fires for
    # session-loaded objects, not a bulk DELETE — so those children are
    # cleared explicitly too, before the accounts themselves.
    conversation_ids_result = await session.execute(
        select(EmailConversation.id).where(EmailConversation.workspace_id == workspace_id)
    )
    conversation_ids = [row[0] for row in conversation_ids_result.all()]
    if conversation_ids:
        await session.execute(
            delete(EmailConversationMessage).where(EmailConversationMessage.conversation_id.in_(conversation_ids))
        )
    await session.execute(delete(EmailConversation).where(EmailConversation.workspace_id == workspace_id))
    await session.execute(delete(EmailDraft).where(EmailDraft.workspace_id == workspace_id))
    await session.execute(delete(DailyEmailQuota).where(DailyEmailQuota.workspace_id == workspace_id))
    await session.execute(delete(EmailAccount).where(EmailAccount.workspace_id == workspace_id))
    await session.execute(delete(EmailMessage).where(EmailMessage.workspace_id == workspace_id))

    sequence_ids_result = await session.execute(select(Sequence.id).where(Sequence.workspace_id == workspace_id))
    sequence_ids = [row[0] for row in sequence_ids_result.all()]
    if sequence_ids:
        await session.execute(delete(SequenceStep).where(SequenceStep.sequence_id.in_(sequence_ids)))
    await session.execute(delete(Sequence).where(Sequence.workspace_id == workspace_id))

    await session.execute(delete(CrmEntry).where(CrmEntry.workspace_id == workspace_id))
    await session.execute(delete(LeadEvent).where(LeadEvent.workspace_id == workspace_id))
    await session.execute(delete(Lead).where(Lead.workspace_id == workspace_id))
    await session.execute(delete(Invitation).where(Invitation.workspace_id == workspace_id))
    await session.execute(delete(FeatureFlagOverride).where(FeatureFlagOverride.workspace_id == workspace_id))
    await session.delete(workspace)
    await session.commit()
