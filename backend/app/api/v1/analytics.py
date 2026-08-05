from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_plan
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.analytics import AnalyticsOverview
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
async def get_overview(
    workspace: Annotated[Workspace, Depends(require_plan("analytics"))],
    session: Annotated[AsyncSession, Depends(get_session)]
):
    data = await analytics_service.compute_overview(session, workspace.id)
    return AnalyticsOverview(**data)
