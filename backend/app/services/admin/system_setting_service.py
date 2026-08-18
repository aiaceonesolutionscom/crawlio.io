import json
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.system_setting import SystemSetting


async def list_settings(session: AsyncSession) -> list[SystemSetting]:
    result = await session.execute(select(SystemSetting).order_by(SystemSetting.key))
    return list(result.scalars().all())


async def ensure_default_settings(session: AsyncSession) -> None:
    """Seed default system settings if they don't already exist."""
    defaults: list[tuple[str, str, str]] = [
        ("site_name", '"Crawlio"', "string"),
        ("primary_color", '"#CBFF4D"', "color"),
        ("secondary_color", '"#A9DE22"', "color"),
        ("hero_video_url", '""', "url"),
        ("cta_text", '"Get Started"', "string"),
        ("feedback_text", '"Trusted by revenue teams worldwide"', "string"),
        ("website_name", '"Crawlio"', "string"),
        ("header_text", '"Lead generation CRM"', "string"),
        ("footer_text", '"Free forever on 700 leads a month. No card, no call."', "string"),
        ("hero_background", '""', "string"),
    ]

    for key, value, value_type in defaults:
        existing = await get_setting(session, key)
        if existing is None:
            await session.execute(
                SystemSetting.__table__.insert().values(
                    key=key,
                    value=value if value_type != "url" else json.loads(value),
                    value_type=value_type,
                    description=f"Default: {key}",
                )
            )

    await session.commit()


async def get_setting(session: AsyncSession, key: str) -> Optional[SystemSetting]:
    result = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
    return result.scalar_one_or_none()


async def get_setting_or_404(session: AsyncSession, key: str) -> SystemSetting:
    setting = await get_setting(session, key)
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No system setting for '{key}'")
    return setting


async def upsert_setting(
    session: AsyncSession,
    *,
    key: str,
    value: Any,
    value_type: str,
    description: Optional[str],
    updated_by: str,
) -> SystemSetting:
    existing = await get_setting(session, key)
    if existing is not None:
        existing.value = value
        existing.value_type = value_type
        if description is not None:
            existing.description = description
        existing.updated_by = updated_by
        await session.commit()
        await session.refresh(existing)
        return existing

    setting = SystemSetting(key=key, value=value, value_type=value_type, description=description, updated_by=updated_by)
    session.add(setting)
    await session.commit()
    await session.refresh(setting)
    return setting


async def delete_setting(session: AsyncSession, key: str) -> None:
    setting = await get_setting_or_404(session, key)
    await session.delete(setting)
    await session.commit()
