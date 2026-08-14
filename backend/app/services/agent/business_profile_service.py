"""Persistent business profile for the AI agent. Stored once on the workspace
during onboarding and reused for every outreach, reply and meeting so the AI
never has to be re-taught the business facts."""

import copy
from datetime import datetime, timezone as _tz
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import BusinessProfile

DEFAULT_HOURS = {
    "monday": ["09:00", "18:00"],
    "tuesday": ["09:00", "18:00"],
    "wednesday": ["09:00", "18:00"],
    "thursday": ["09:00", "18:00"],
    "friday": ["09:00", "18:00"],
    "saturday": ["10:00", "14:00"],
}


async def get_profile(session: AsyncSession, workspace_id: str) -> Optional[BusinessProfile]:
    result = await session.execute(
        select(BusinessProfile).where(BusinessProfile.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()


async def create_profile(
    session: AsyncSession,
    workspace_id: str,
    business_name: str,
    owner_name: str,
    business_phone: Optional[str] = None,
    business_address: Optional[str] = None,
    services: str = "",
    website: Optional[str] = None,
    timezone: str = "Asia/Karachi",
    knowledge_base: str = "",
) -> BusinessProfile:
    profile = BusinessProfile(
        workspace_id=workspace_id,
        business_name=business_name,
        owner_name=owner_name,
        business_phone=business_phone,
        business_address=business_address,
        services=services,
        website=website,
        timezone=timezone,
        business_hours=copy.deepcopy(DEFAULT_HOURS),
        knowledge_base=knowledge_base,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


async def update_profile(
    session: AsyncSession,
    profile: BusinessProfile,
    business_name: Optional[str] = None,
    owner_name: Optional[str] = None,
    business_phone: Optional[str] = None,
    business_address: Optional[str] = None,
    services: Optional[str] = None,
    website: Optional[str] = None,
    timezone: Optional[str] = None,
    business_hours: Optional[dict] = None,
    knowledge_base: Optional[str] = None,
) -> BusinessProfile:
    if business_name is not None:
        profile.business_name = business_name
    if owner_name is not None:
        profile.owner_name = owner_name
    if business_phone is not None:
        profile.business_phone = business_phone
    if business_address is not None:
        profile.business_address = business_address
    if services is not None:
        profile.services = services
    if website is not None:
        profile.website = website
    if timezone is not None:
        profile.timezone = timezone
    if business_hours is not None:
        profile.business_hours = business_hours
    if knowledge_base is not None:
        profile.knowledge_base = knowledge_base
    profile.updated_at = datetime.now(_tz.utc)
    await session.commit()
    await session.refresh(profile)
    return profile


def to_context(profile: BusinessProfile, user_email: str = "") -> str:
    """Plain-language business context injected into every agent prompt."""
    hours = profile.business_hours or DEFAULT_HOURS
    hours_lines = [
        f"  {day.title()}: {v[0]} - {v[1]}" if isinstance(v, list) and len(v) >= 2 else f"  {day.title()}: closed"
        for day, v in hours.items()
    ]
    context = (
        f"Business: {profile.business_name}\n"
        f"Owner/Representative: {profile.owner_name}\n"
        f"Business phone: {profile.business_phone or 'N/A'}\n"
        f"Business address: {profile.business_address or 'N/A'}\n"
        f"Services: {profile.services or 'N/A'}\n"
        f"Website: {profile.website or 'N/A'}\n"
        f"Timezone: {profile.timezone}\n"
        f"Business hours:\n" + "\n".join(hours_lines)
    )
    if profile.knowledge_base:
        context += f"\nKnowledge base:\n{profile.knowledge_base}"
    if user_email:
        context += f"\nBusiness email (sender): {user_email}"
    return context