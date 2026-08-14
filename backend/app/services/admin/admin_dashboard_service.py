from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import as_utc
from app.db.models.lead import Lead
from app.db.models.platform_admin import PlatformAdmin
from app.db.models.workspace import Workspace


async def compute_overview(session: AsyncSession) -> dict[str, Any]:
    total_workspaces_result = await session.execute(select(func.count()).select_from(Workspace))
    total_workspaces = total_workspaces_result.scalar_one()

    plan_counts_result = await session.execute(select(Workspace.plan, func.count()).group_by(Workspace.plan))
    workspaces_by_plan = [{"plan": plan, "count": count} for plan, count in plan_counts_result.all()]

    total_leads_result = await session.execute(select(func.count()).select_from(Lead))
    total_leads = total_leads_result.scalar_one()

    active_admins_result = await session.execute(
        select(func.count()).select_from(PlatformAdmin).where(PlatformAdmin.is_active.is_(True))
    )
    active_platform_admins = active_admins_result.scalar_one()

    created_at_result = await session.execute(select(Workspace.created_at))
    created_ats = [row[0] for row in created_at_result.all()]

    now = datetime.now(timezone.utc)
    new_workspaces_over_time = []
    for i in range(7, -1, -1):
        start = now - timedelta(weeks=i + 1)
        # Inclusive upper bound from the start — see analytics_service.py's
        # leads_over_time, which had to be patched after a strict `<` silently
        # dropped workspaces created in the same instant as this "now" capture.
        end = now - timedelta(weeks=i)
        count = sum(1 for created_at in created_ats if start <= as_utc(created_at) <= end)
        new_workspaces_over_time.append({"week": f"W{8 - i}", "count": count})

    return {
        "total_workspaces": total_workspaces,
        "workspaces_by_plan": workspaces_by_plan,
        "total_leads": total_leads,
        "new_workspaces_over_time": new_workspaces_over_time,
        "active_platform_admins": active_platform_admins,
    }
