from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_deps import require_super_admin
from app.db.models.platform_admin import PlatformAdmin
from app.db.session import get_session
from app.schemas.admin import AdminDashboardOverview
from app.services import admin_dashboard_service

router = APIRouter(prefix="/dashboard", tags=["admin:dashboard"])


@router.get("/overview", response_model=AdminDashboardOverview)
async def get_dashboard_overview(
    admin: Annotated[PlatformAdmin, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await admin_dashboard_service.compute_overview(session)
