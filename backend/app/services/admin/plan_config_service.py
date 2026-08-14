from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.plan_config import PlanConfig

# No caching in Phase 1: this is a single indexed-column lookup, and an admin's
# edit should take effect immediately with zero invalidation logic. Revisit
# only if this is later measured to be a hot path.


async def get_plan_config(session: AsyncSession, plan_key: str) -> Optional[PlanConfig]:
    result = await session.execute(select(PlanConfig).where(PlanConfig.plan_key == plan_key))
    return result.scalar_one_or_none()


async def get_plan_config_or_404(session: AsyncSession, plan_key: str) -> PlanConfig:
    config = await get_plan_config(session, plan_key)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No plan config for '{plan_key}'")
    return config


async def get_capabilities(session: AsyncSession, plan_key: str) -> set[str]:
    config = await get_plan_config(session, plan_key)
    if config is None:
        return set()
    return set(config.capabilities)


async def list_plan_configs(session: AsyncSession) -> list[PlanConfig]:
    result = await session.execute(select(PlanConfig).order_by(PlanConfig.sort_order))
    return list(result.scalars().all())


async def update_plan_config(session: AsyncSession, plan_key: str, **fields) -> PlanConfig:
    config = await get_plan_config(session, plan_key)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No plan config for '{plan_key}'")
    for key, value in fields.items():
        if value is not None:
            setattr(config, key, value)
    await session.commit()
    await session.refresh(config)
    return config
