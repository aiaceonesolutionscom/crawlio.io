from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id, get_current_workspace
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.workspace import WorkspaceCreate, WorkspacePlanUpdate, WorkspaceRead
from app.services import workspace_service

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    user_id: Annotated[str, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)]
):
    return await workspace_service.create_workspace(session, user_id, payload)


@router.get("/me", response_model=WorkspaceRead)
async def read_my_workspace(workspace: Annotated[Workspace, Depends(get_current_workspace)]):
    return workspace


@router.patch("/{workspace_id}/plan", response_model=WorkspaceRead)
async def update_plan(
    workspace_id: str,
    payload: WorkspacePlanUpdate,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)]
):
    if workspace.id != workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your workspace")
    return await workspace_service.change_plan(session, workspace, payload.plan)
