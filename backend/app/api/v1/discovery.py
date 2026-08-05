import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, require_plan
from app.core.plans import DISCOVERY_LIMITS, PLAN_CAPABILITIES
from app.db.session import get_session
from app.db.models.workspace import Workspace
from app.schemas.discovery import (
    DiscoveredLead,
    DiscoverRequest,
    DiscoverResponse,
    DiscoveryImportRequest,
    DiscoveryImportResult,
    DiscoveryImportSkip,
)
from app.schemas.lead import LeadCreate, lead_to_read
from app.services import discovery_service, geo_service, tavily_service
from app.services.lead_service import DuplicateLeadError, create_lead

router = APIRouter(prefix="/leads/discover", tags=["lead-discovery"])

# How many results (missing an email) get a Tavily enrichment lookup per search.
# Bounded to keep latency and Tavily usage predictable.
MAX_ENRICHED_PER_SEARCH = 15


@router.post("", response_model=DiscoverResponse)
async def discover(
    payload: DiscoverRequest,
    workspace: Annotated[Workspace, Depends(require_plan("lead_discovery"))],
):
    limit = DISCOVERY_LIMITS.get(workspace.plan, 50)
    try:
        results = await discovery_service.discover_businesses(payload.niche, payload.lat, payload.lon, limit=limit)
    except discovery_service.DiscoveryUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    enhanced = "lead_discovery_enhanced" in PLAN_CAPABILITIES.get(workspace.plan, set())
    if enhanced:
        country_name = geo_service.country_name_for_code(payload.country) or payload.country
        results = await _enrich_missing_emails(results, payload.city, country_name)

    items = [DiscoveredLead(**r) for r in results]
    return DiscoverResponse(items=items, total=len(items), limit=limit, enhanced=enhanced)


async def _enrich_missing_emails(results: list[dict], city: str, country_name: str) -> list[dict]:
    to_enrich = [r for r in results if not r.get("email")][:MAX_ENRICHED_PER_SEARCH]
    if not to_enrich:
        return results

    lookups = await asyncio.gather(
        *(tavily_service.find_contact_email(r["name"], city, country_name) for r in to_enrich),
        return_exceptions=True,
    )
    for result, email in zip(to_enrich, lookups):
        if isinstance(email, str):
            result["email"] = email
    return results


@router.post("/import", response_model=DiscoveryImportResult)
async def import_discovered(
    payload: DiscoveryImportRequest,
    workspace: Annotated[Workspace, Depends(require_plan("lead_discovery"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    created = []
    skipped = []

    for item in payload.items:
        try:
            lead = await create_lead(
                session,
                workspace,
                LeadCreate(
                    name=item.name,
                    email=item.email,
                    phone=item.phone,
                    website=item.website,
                    address=item.address,
                    source=f"Lead Discovery ({item.source})",
                ),
            )
            created.append(lead_to_read(lead))
        except DuplicateLeadError:
            skipped.append(DiscoveryImportSkip(name=item.name, reason="duplicate"))
        except HTTPException as exc:
            if exc.status_code == status.HTTP_403_FORBIDDEN:
                skipped.append(DiscoveryImportSkip(name=item.name, reason="quota_exceeded"))
                break
            raise

    return DiscoveryImportResult(created=created, skipped=skipped)
