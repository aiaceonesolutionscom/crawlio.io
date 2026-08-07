from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.crm import CrmEntry
from app.db.models.lead import Lead


async def ai_filter_leads(session: AsyncSession, workspace_id: str) -> tuple[list[Lead], list[Lead]]:
    """Splits every lead in the workspace into two buckets by website presence,
    each sorted by the AI score already computed at lead-creation time (highest
    first) — no new AI call, just a smart view over existing data."""
    result = await session.execute(select(Lead).where(Lead.workspace_id == workspace_id))
    leads = list(result.scalars().all())

    def score_key(lead: Lead) -> int:
        return lead.score if lead.score is not None else -1

    with_website = sorted((l for l in leads if l.website), key=score_key, reverse=True)
    without_website = sorted((l for l in leads if not l.website), key=score_key, reverse=True)
    return with_website, without_website


async def add_to_crm(session: AsyncSession, workspace_id: str, lead_ids: list[str]) -> tuple[int, int]:
    added = 0
    skipped = 0
    for lead_id in lead_ids:
        lead_result = await session.execute(
            select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id)
        )
        lead = lead_result.scalar_one_or_none()
        if lead is None:
            skipped += 1
            continue

        existing = await session.execute(
            select(CrmEntry).where(CrmEntry.workspace_id == workspace_id, CrmEntry.lead_id == lead_id)
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        session.add(
            CrmEntry(
                workspace_id=workspace_id,
                lead_id=lead_id,
                category="with_website" if lead.website else "no_website",
            )
        )
        added += 1
    await session.commit()
    return added, skipped


async def list_crm_entries(session: AsyncSession, workspace_id: str) -> list[CrmEntry]:
    result = await session.execute(
        select(CrmEntry)
        .where(CrmEntry.workspace_id == workspace_id)
        .options(selectinload(CrmEntry.lead))
        .order_by(CrmEntry.added_at.desc())
    )
    entries = list(result.scalars().all())
    # Defensive: an entry whose lead was deleted through some other path
    # (backfilled data, a future bulk-delete route, etc.) would otherwise
    # crash the response instead of just quietly not showing it.
    return [e for e in entries if e.lead is not None]
