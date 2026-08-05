from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_plan
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.team import InviteMemberCreate, TeamEntryRead, TeamListResponse
from app.services import quota_service, team_service

router = APIRouter(prefix="/team", tags=["team"])


@router.get("/members", response_model=TeamListResponse)
async def list_members(
    workspace: Annotated[Workspace, Depends(require_plan("team"))],
    session: Annotated[AsyncSession, Depends(get_session)]
):
    items = await team_service.list_team(session, workspace.id)
    seats_used = await quota_service.count_seats(session, workspace.id)
    return TeamListResponse(items=items, seats_used=seats_used, seat_quota=workspace.seat_quota)


@router.post("/invites", response_model=TeamEntryRead, status_code=status.HTTP_201_CREATED)
async def create_invite(
    payload: InviteMemberCreate,
    workspace: Annotated[Workspace, Depends(require_plan("team"))],
    session: Annotated[AsyncSession, Depends(get_session)]
):
    return await team_service.invite_member(session, workspace, payload.email, payload.role)


@router.delete("/members/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    entry_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("team"))],
    session: Annotated[AsyncSession, Depends(get_session)]
):
    removed = await team_service.remove_entry(session, workspace.id, entry_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
