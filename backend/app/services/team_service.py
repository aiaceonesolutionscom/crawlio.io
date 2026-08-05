from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.invitation import Invitation
from app.db.models.workspace import Workspace, WorkspaceMember
from app.schemas.team import TeamEntryRead
from app.services import quota_service
from app.workers.tasks_email import send_invite_email_task


def _member_to_entry(member: WorkspaceMember) -> TeamEntryRead:
    return TeamEntryRead(
        id=member.id, name=member.name, email=member.email, role=member.role, status="Active",
        created_at=member.created_at
    )


def _invitation_to_entry(invitation: Invitation) -> TeamEntryRead:
    return TeamEntryRead(
        id=invitation.id, name=None, email=invitation.email, role=invitation.role, status="Invited",
        created_at=invitation.created_at
    )


async def list_team(session: AsyncSession, workspace_id: str) -> list[TeamEntryRead]:
    members_result = await session.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
    )
    invites_result = await session.execute(
        select(Invitation).where(Invitation.workspace_id == workspace_id, Invitation.status == "pending")
    )
    entries = [_member_to_entry(m) for m in members_result.scalars().all()]
    entries += [_invitation_to_entry(i) for i in invites_result.scalars().all()]
    entries.sort(key=lambda e: e.created_at)
    return entries


async def invite_member(session: AsyncSession, workspace: Workspace, email: str, role: str) -> TeamEntryRead:
    await quota_service.check_seat_quota(session, workspace)

    existing_member = await session.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace.id, WorkspaceMember.email == email)
    )
    if existing_member.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already a member of this workspace")

    existing_invite = await session.execute(
        select(Invitation).where(
            Invitation.workspace_id == workspace.id, Invitation.email == email, Invitation.status == "pending"
        )
    )
    if existing_invite.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already invited")

    invitation = Invitation(workspace_id=workspace.id, email=email, role=role, status="pending")
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)

    send_invite_email_task.delay(email, workspace.name, role)

    return _invitation_to_entry(invitation)


async def remove_entry(session: AsyncSession, workspace_id: str, entry_id: str) -> bool:
    invite_result = await session.execute(
        select(Invitation).where(Invitation.id == entry_id, Invitation.workspace_id == workspace_id)
    )
    invitation = invite_result.scalar_one_or_none()
    if invitation is not None:
        await session.delete(invitation)
        await session.commit()
        return True

    member_result = await session.execute(
        select(WorkspaceMember).where(WorkspaceMember.id == entry_id, WorkspaceMember.workspace_id == workspace_id)
    )
    member = member_result.scalar_one_or_none()
    if member is None:
        return False
    if member.role == "Owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the workspace owner")

    await session.delete(member)
    await session.commit()
    return True
