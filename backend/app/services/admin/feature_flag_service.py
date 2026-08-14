from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.feature_flag import FeatureFlag, FeatureFlagOverride

# No caching in Phase 1, same rationale as plan_config_service: a single
# indexed lookup, and an admin's toggle should take effect immediately.


async def list_flags(session: AsyncSession) -> list[FeatureFlag]:
    result = await session.execute(select(FeatureFlag).order_by(FeatureFlag.key))
    return list(result.scalars().all())


async def get_flag_or_404(session: AsyncSession, flag_id: str) -> FeatureFlag:
    result = await session.execute(select(FeatureFlag).where(FeatureFlag.id == flag_id))
    flag = result.scalar_one_or_none()
    if flag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature flag not found")
    return flag


async def get_flag_by_key(session: AsyncSession, key: str) -> Optional[FeatureFlag]:
    result = await session.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    return result.scalar_one_or_none()


async def create_flag(session: AsyncSession, *, key: str, description: Optional[str], default_enabled: bool) -> FeatureFlag:
    if await get_flag_by_key(session, key) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Flag '{key}' already exists")
    flag = FeatureFlag(key=key, description=description, default_enabled=default_enabled)
    session.add(flag)
    await session.commit()
    await session.refresh(flag)
    return flag


async def update_flag(session: AsyncSession, flag_id: str, **fields) -> FeatureFlag:
    flag = await get_flag_or_404(session, flag_id)
    for key, value in fields.items():
        if value is not None:
            setattr(flag, key, value)
    await session.commit()
    await session.refresh(flag)
    return flag


async def delete_flag(session: AsyncSession, flag: FeatureFlag) -> None:
    await session.execute(delete(FeatureFlagOverride).where(FeatureFlagOverride.flag_id == flag.id))
    await session.delete(flag)
    await session.commit()


async def list_overrides_for_flag(session: AsyncSession, flag_id: str) -> list[FeatureFlagOverride]:
    result = await session.execute(
        select(FeatureFlagOverride).where(FeatureFlagOverride.flag_id == flag_id).order_by(FeatureFlagOverride.workspace_id)
    )
    return list(result.scalars().all())


async def get_override(session: AsyncSession, flag_id: str, workspace_id: str) -> Optional[FeatureFlagOverride]:
    result = await session.execute(
        select(FeatureFlagOverride).where(
            FeatureFlagOverride.flag_id == flag_id, FeatureFlagOverride.workspace_id == workspace_id
        )
    )
    return result.scalar_one_or_none()


async def set_override(session: AsyncSession, *, flag_id: str, workspace_id: str, is_enabled: bool) -> FeatureFlagOverride:
    existing = await get_override(session, flag_id, workspace_id)
    if existing is not None:
        existing.is_enabled = is_enabled
        await session.commit()
        await session.refresh(existing)
        return existing

    override = FeatureFlagOverride(flag_id=flag_id, workspace_id=workspace_id, is_enabled=is_enabled)
    session.add(override)
    await session.commit()
    await session.refresh(override)
    return override


async def clear_override(session: AsyncSession, flag_id: str, workspace_id: str) -> None:
    existing = await get_override(session, flag_id, workspace_id)
    if existing is not None:
        await session.delete(existing)
        await session.commit()


async def is_enabled(session: AsyncSession, key: str, workspace_id: str) -> bool:
    """Effective state for a workspace: an override always wins over the flag's
    default. Unknown key fails closed (False) rather than 404ing — this is meant
    to be called from hot request paths, not admin screens."""
    flag = await get_flag_by_key(session, key)
    if flag is None:
        return False
    override = await get_override(session, flag.id, workspace_id)
    if override is not None:
        return override.is_enabled
    return flag.default_enabled
