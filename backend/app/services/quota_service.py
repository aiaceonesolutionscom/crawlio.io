from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.lead import Lead
from app.db.models.workspace import Workspace


async def check_lead_quota(session: AsyncSession, workspace: Workspace) -> None:
    result = await session.execute(
        select(func.count()).select_from(Lead).where(Lead.workspace_id == workspace.id)
    )
    count = result.scalar_one()
    if count >= workspace.lead_quota:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Lead quota reached ({workspace.lead_quota} for the {workspace.plan} plan). "
                "Upgrade to add more leads."
            )
        )
