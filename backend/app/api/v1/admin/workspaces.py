from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_deps import require_permission
from app.core.permissions import PERMISSION_WORKSPACES_READ, PERMISSION_WORKSPACES_WRITE
from app.db.models.platform_admin import PlatformAdmin
from app.db.session import get_session
from app.schemas.admin import AdminWorkspaceRead, AdminWorkspaceUpdate
from app.services.admin import audit_service
from app.services.workspace import workspace_service

router = APIRouter(prefix="/workspaces", tags=["admin:workspaces"])


def _snapshot(workspace) -> dict:
    return {
        "name": workspace.name,
        "plan": workspace.plan,
        "lead_quota": workspace.lead_quota,
        "seat_quota": workspace.seat_quota,
    }


@router.get("", response_model=list[AdminWorkspaceRead])
async def list_workspaces(
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_WORKSPACES_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    workspaces = await workspace_service.list_all_workspaces(session, search=search, limit=limit, offset=offset)
    usage = await workspace_service.workspace_usage_counts(session, [w.id for w in workspaces])
    for workspace in workspaces:
        counts = usage.get(workspace.id, {"member_count": 0, "lead_count": 0, "email_count": 0})
        workspace.member_count = counts["member_count"]
        workspace.lead_count = counts["lead_count"]
        workspace.email_count = counts["email_count"]
    return workspaces


@router.get("/{workspace_id}", response_model=AdminWorkspaceRead)
async def get_workspace(
    workspace_id: str,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_WORKSPACES_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    workspace = await workspace_service.get_workspace_by_id(session, workspace_id)
    usage = await workspace_service.workspace_usage_counts(session, [workspace.id])
    counts = usage.get(workspace.id, {"member_count": 0, "lead_count": 0, "email_count": 0})
    workspace.member_count = counts["member_count"]
    workspace.lead_count = counts["lead_count"]
    workspace.email_count = counts["email_count"]
    return workspace


@router.patch("/{workspace_id}", response_model=AdminWorkspaceRead)
async def update_workspace(
    workspace_id: str,
    payload: AdminWorkspaceUpdate,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_WORKSPACES_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    workspace = await workspace_service.get_workspace_by_id(session, workspace_id)
    before = _snapshot(workspace)
    updated = await workspace_service.admin_update_workspace(
        session,
        workspace,
        name=payload.name,
        plan=payload.plan,
        lead_quota=payload.lead_quota,
        seat_quota=payload.seat_quota,
    )
    await audit_service.record_action(
        session,
        actor=admin,
        action="workspace.update",
        target_type="workspace",
        target_id=workspace_id,
        workspace_id=workspace_id,
        before=before,
        after=_snapshot(updated),
        ip_address=request.client.host if request.client else None,
    )
    return updated


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: str,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_WORKSPACES_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    workspace = await workspace_service.get_workspace_by_id(session, workspace_id)
    before = _snapshot(workspace)
    await workspace_service.delete_workspace(session, workspace)
    await audit_service.record_action(
        session,
        actor=admin,
        action="workspace.delete",
        target_type="workspace",
        target_id=workspace_id,
        workspace_id=workspace_id,
        before=before,
        ip_address=request.client.host if request.client else None,
    )
