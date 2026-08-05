from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_plan
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.automation import (
    SequenceCreate,
    SequenceListResponse,
    SequenceRead,
    SequenceStatusUpdate
)
from app.services import automation_service

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/sequences", response_model=SequenceListResponse)
async def list_sequences(
    workspace: Annotated[Workspace, Depends(require_plan("automation"))],
    session: Annotated[AsyncSession, Depends(get_session)]
):
    items = await automation_service.list_sequences(session, workspace.id)
    return SequenceListResponse(items=items)


@router.post("/sequences", response_model=SequenceRead, status_code=status.HTTP_201_CREATED)
async def create_sequence(
    payload: SequenceCreate,
    workspace: Annotated[Workspace, Depends(require_plan("automation"))],
    session: Annotated[AsyncSession, Depends(get_session)]
):
    return await automation_service.create_sequence(session, workspace.id, payload)


@router.patch("/sequences/{sequence_id}/status", response_model=SequenceRead)
async def update_sequence_status(
    sequence_id: str,
    payload: SequenceStatusUpdate,
    workspace: Annotated[Workspace, Depends(require_plan("automation"))],
    session: Annotated[AsyncSession, Depends(get_session)]
):
    sequence = await automation_service.get_sequence(session, workspace.id, sequence_id)
    if sequence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")
    return await automation_service.update_status(session, sequence, payload.status)


@router.delete("/sequences/{sequence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sequence(
    sequence_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("automation"))],
    session: Annotated[AsyncSession, Depends(get_session)]
):
    sequence = await automation_service.get_sequence(session, workspace.id, sequence_id)
    if sequence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")
    await automation_service.delete_sequence(session, sequence)
