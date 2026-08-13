"""Meeting availability + booking for the AI agent.

Slots are ALWAYS derived from the workspace BusinessProfile (business_hours +
timezone) minus already-booked meetings — never invented by the LLM. The LLM
only picks from the concrete slot list this service returns."""

import uuid
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import BusinessProfile, Meeting

SLOT_MINUTES = 30
DAYS_AHEAD = 5


def _parse_hhmm(value: str) -> Optional[int]:
    parts = value.split(":")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return None


def _as_tz(dt: datetime, tz: ZoneInfo) -> datetime:
    """DB datetimes may be naive (SQLite strips tz) or aware (Postgres).
    Naive stored values are local wall-clock in the profile's timezone."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def _as_naive_local(dt: datetime) -> datetime:
    """Normalize any stored datetime to a server-local naive value so
    comparisons never mix aware and naive."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone().replace(tzinfo=None)


def next_slots(
    profile: BusinessProfile,
    now: Optional[datetime] = None,
    count: int = 4,
    bookable: Optional[list[datetime]] = None,
) -> list[datetime]:
    """Return the next `count` concrete slot datetimes in the profile's timezone,
    each a duration of SLOT_MINUTES within business hours, excluding times that
    collide with already-booked meetings."""
    tz = ZoneInfo(profile.timezone) if profile.timezone else ZoneInfo("Asia/Karachi")
    now = (now or datetime.now(tz)).astimezone(tz)
    bookable = [_as_tz(b, tz) for b in (bookable or [])]

    slots: list[datetime] = []
    cursor = now.replace(minute=(now.minute // SLOT_MINUTES) * SLOT_MINUTES, second=0, microsecond=0)
    seen_days = 0
    guard = 0
    while len(slots) < count and seen_days <= DAYS_AHEAD and guard < 500:
        guard += 1
        day_name = cursor.strftime("%A").lower()
        day_hours = (profile.business_hours or {}).get(day_name) or []
        if not isinstance(day_hours, list) or len(day_hours) < 2:
            cursor += timedelta(hours=1)
            continue

        start_min = _parse_hhmm(day_hours[0])
        end_min = _parse_hhmm(day_hours[1])
        if start_min is None or end_min is None:
            cursor += timedelta(hours=1)
            continue

        day_start = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        # Reset to the day's opening time once we've moved past a full day.
        if cursor < day_start + timedelta(minutes=start_min):
            cursor = day_start + timedelta(minutes=start_min)

        while cursor < day_start + timedelta(minutes=end_min) and len(slots) < count:
            if cursor > now and not any(cursor < b + timedelta(minutes=SLOT_MINUTES) and b < cursor + timedelta(minutes=SLOT_MINUTES) for b in bookable):
                slots.append(cursor)
            cursor += timedelta(minutes=SLOT_MINUTES)

        seen_days += 1
        cursor = day_start + timedelta(days=1)
    return slots


async def book_meeting(
    session: AsyncSession,
    workspace_id: str,
    lead_id: str,
    scheduled_at: datetime,
    conversation_id: Optional[str] = None,
    lead_name: str = "",
    lead_email: str = "",
) -> Meeting:
    booking_ref = f"BKG-{uuid.uuid4().hex[:8].upper()}"
    meeting = Meeting(
        workspace_id=workspace_id,
        lead_id=lead_id,
        conversation_id=conversation_id,
        booking_ref=booking_ref,
        scheduled_at=scheduled_at,
        status="booked",
        lead_name=lead_name,
        lead_email=lead_email,
    )
    session.add(meeting)
    return meeting


async def list_bookable_meetings(session: AsyncSession, workspace_id: str) -> list[datetime]:
    from datetime import timedelta

    result = await session.execute(
        select(Meeting).where(
            Meeting.workspace_id == workspace_id,
            Meeting.status == "booked",
        )
    )
    meetings = list(result.scalars().all())
    horizon = datetime.now() + timedelta(days=DAYS_AHEAD + 1)
    return [m.scheduled_at for m in meetings if m.scheduled_at and _as_naive_local(m.scheduled_at) < horizon]