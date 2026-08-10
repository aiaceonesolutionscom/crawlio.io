from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.lead import Lead

STATUSES = ["New", "Qualified", "Contacted", "Nurturing", "Won", "Lost"]


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _is_qualified(lead: Lead) -> bool:
    return lead.status == "Qualified" or (lead.score is not None and lead.score >= 70)


async def compute_overview(session: AsyncSession, workspace_id: str) -> dict[str, Any]:
    result = await session.execute(select(Lead).where(Lead.workspace_id == workspace_id))
    leads = list(result.scalars().all())

    total_leads = len(leads)
    scored = [lead.score for lead in leads if lead.score is not None]
    qualified_leads = sum(1 for lead in leads if _is_qualified(lead))
    avg_score = round(sum(scored) / len(scored), 1) if scored else 0.0

    now = datetime.now(timezone.utc)
    leads_over_time = []
    for i in range(7, -1, -1):
        start = now - timedelta(weeks=i + 1)
        # Inclusive upper bound: a lead created in the same instant this "now"
        # was captured (clock resolution ties are common on Windows) must still
        # land in the current bucket rather than falling through every range.
        end = now - timedelta(weeks=i)
        week_leads = [lead for lead in leads if start <= _as_utc(lead.created_at) <= end]
        leads_over_time.append({
            "week": f"W{8 - i}",
            "leads": len(week_leads),
            "qualified": sum(1 for lead in week_leads if _is_qualified(lead))
        })

    source_counts: dict[str, int] = defaultdict(int)
    for lead in leads:
        source_counts[lead.source or "Unknown"] += 1
    top_sources = sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)[:4]
    source_split = [
        {"name": name, "value": round(count / total_leads * 100) if total_leads else 0}
        for name, count in top_sources
    ]

    status_counts = {status_label: 0 for status_label in STATUSES}
    for lead in leads:
        status_counts[lead.status] = status_counts.get(lead.status, 0) + 1
    status_breakdown = [{"status": status_label, "count": count} for status_label, count in status_counts.items()]

    return {
        "total_leads": total_leads,
        "qualified_leads": qualified_leads,
        "avg_score": avg_score,
        "leads_over_time": leads_over_time,
        "source_split": source_split,
        "status_breakdown": status_breakdown
    }
