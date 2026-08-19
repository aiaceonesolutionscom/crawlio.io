import asyncio
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, require_plan
from app.core.plans import PLAN_CAPABILITIES
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.crm import AiFilterResponse
from app.schemas.lead import (
    LeadCreate,
    LeadEmailResponse,
    LeadEnrichDispatchResult,
    LeadEnrichRequest,
    LeadListResponse,
    LeadRead,
    LeadUpdate,
    LeadWhatsAppResponse,
    lead_to_read,
)
from app.services.crm import crm_service
from app.services.enrichment import enrichment_pipeline
from app.services.lead import lead_service
from app.services.lead.lead_service import DuplicateLeadError

from app.workers.tasks_enrichment import enrich_lead
from app.workers.tasks_scoring import score_lead_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads", tags=["leads"])

# How many selected leads get a per-lead enrichment pass in one request —
# bounded so a large bulk selection can't turn into dozens of concurrent
# outbound HTTP calls (one website fetch per lead).
MAX_ENRICH_PER_REQUEST = 30


def _duplicate_error(field: str) -> HTTPException:
    label = "email address" if field == "email" else "phone number"
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"A lead with this {label} already exists in your workspace",
    )


@router.get("", response_model=LeadListResponse)
async def list_leads(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    leads, total = await lead_service.list_leads(session, workspace.id, search, page=page, limit=limit)
    return LeadListResponse(
        items=[lead_to_read(lead) for lead in leads],
        total=total,
        page=page,
        limit=limit,
    )


@router.delete("")
async def delete_all_leads(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    deleted = await lead_service.delete_all_leads(session, workspace.id)
    return {"deleted": deleted}


@router.get("/export")
async def export_leads(
    workspace: Annotated[Workspace, Depends(require_plan("export"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Optional[str] = Query(default=None),
):
    csv_data = await lead_service.export_leads_csv(session, workspace.id, search)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="leads-export.csv"'},
    )


@router.get("/ai-filter", response_model=AiFilterResponse)
async def ai_filter_leads(
    workspace: Annotated[Workspace, Depends(require_plan("ai_lead_filter"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    with_website, without_website = await crm_service.ai_filter_leads(session, workspace.id)
    return AiFilterResponse(
        with_website=[lead_to_read(l) for l in with_website],
        without_website=[lead_to_read(l) for l in without_website],
    )


@router.post("/enrich", response_model=LeadEnrichDispatchResult)
async def enrich_leads(
    payload: LeadEnrichRequest,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Re-run full enrichment on leads that already exist — useful for leads
    that were added manually, imported incomplete, or missed contact info the
    first time. Never overwrites data that's already there, only fills gaps and
    adds richer profile fields (hours/description/socials).

    Tries to dispatch each lead to the background worker first (fast,
    non-blocking, matching /ai-filter/enrich); if the worker isn't reachable
    (Redis down), falls back to running the same enrichment pipeline
    synchronously in this request instead of losing the work. The response is
    a "dispatched" count, not a completed-enrichment count — the client is
    expected to refresh after a short wait to see the results, same as
    /ai-filter/enrich."""
    lead_ids = payload.lead_ids[:MAX_ENRICH_PER_REQUEST]
    leads = await lead_service.get_leads_by_ids(session, workspace.id, lead_ids)
    enhanced = "lead_discovery_enhanced" in PLAN_CAPABILITIES.get(workspace.plan, set())

    fallback_leads = []
    for lead in leads:
        try:
            enrich_lead.delay(lead.id)
        except Exception as exc:
            logger.warning("Could not dispatch background enrichment for lead %s: %s", lead.id, exc)
            fallback_leads.append(lead)

    if fallback_leads:
        semaphore = asyncio.Semaphore(4)

        async def _enrich_one(lead) -> dict:
            async with semaphore:
                metadata = dict(lead.lead_metadata or {})
                item = {
                    "name": lead.name,
                    "phone": lead.phone,
                    "email": lead.email,
                    "website": lead.website,
                    "address": lead.address or metadata.get("address"),
                    "social_links": metadata.get("social_links") or {},
                }
                return await enrichment_pipeline.enrich_item(
                    item,
                    city=lead.address or "",
                    country="",
                    country_code=None,
                    use_browser=enhanced,
                    use_ai=enhanced,
                    use_google_maps=True,
                )

        outcomes = await asyncio.gather(*(_enrich_one(lead) for lead in fallback_leads), return_exceptions=True)
        for lead, outcome in zip(fallback_leads, outcomes):
            if not isinstance(outcome, dict) or not outcome:
                continue
            lead_service.apply_enrichment_to_lead(lead, outcome)
            metadata = dict(lead.lead_metadata or {})
            if outcome.get("address"):
                lead.address = lead.address or outcome["address"]
            for key in ("description", "hours", "completeness", "enrichment_source", "last_enriched_at"):
                if outcome.get(key):
                    metadata[key] = outcome[key]
            metadata["enrichment_status"] = outcome.get("enrichment_status") or "done"
            lead.lead_metadata = metadata or None
        await session.commit()

    return LeadEnrichDispatchResult(dispatched=len(leads))


@router.post("/ai-filter/enrich")
async def ai_filter_enrich(
    payload: LeadEnrichRequest,
    workspace: Annotated[Workspace, Depends(require_plan("ai_lead_filter"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Enrich leads from the "Filter your leads" view. Tries to dispatch each
    lead to the background worker first (fast, non-blocking); if the worker
    isn't reachable (Redis down), falls back to running the same enrichment
    pipeline synchronously in this request instead of losing the work — the
    "dispatched" count means "queued or completed", either way real work
    happened rather than a silent no-op, and the frontend's existing
    "refresh to see updates" messaging stays accurate either way."""
    lead_ids = payload.lead_ids[:MAX_ENRICH_PER_REQUEST]
    leads = await lead_service.get_leads_by_ids(session, workspace.id, lead_ids)
    enhanced = "lead_discovery_enhanced" in PLAN_CAPABILITIES.get(workspace.plan, set())

    fallback_leads = []
    for lead in leads:
        try:
            enrich_lead.delay(lead.id)
        except Exception as exc:
            logger.warning("Could not dispatch background enrichment for lead %s: %s", lead.id, exc)
            fallback_leads.append(lead)

    if fallback_leads:
        semaphore = asyncio.Semaphore(4)

        async def _enrich_one(lead) -> dict:
            async with semaphore:
                metadata = dict(lead.lead_metadata or {})
                item = {
                    "name": lead.name,
                    "phone": lead.phone,
                    "email": lead.email,
                    "website": lead.website,
                    "address": lead.address or metadata.get("address"),
                    "social_links": metadata.get("social_links") or {},
                }
                return await enrichment_pipeline.enrich_item(
                    item,
                    city=lead.address or "",
                    country="",
                    country_code=None,
                    use_browser=enhanced,
                    use_ai=enhanced,
                )

        outcomes = await asyncio.gather(*(_enrich_one(lead) for lead in fallback_leads), return_exceptions=True)
        for lead, outcome in zip(fallback_leads, outcomes):
            if not isinstance(outcome, dict) or not outcome:
                continue
            lead_service.apply_enrichment_to_lead(lead, outcome)
            metadata = dict(lead.lead_metadata or {})
            if outcome.get("address"):
                lead.address = lead.address or outcome["address"]
            for key in ("description", "hours", "completeness", "enrichment_source", "last_enriched_at"):
                if outcome.get(key):
                    metadata[key] = outcome[key]
            metadata["enrichment_status"] = outcome.get("enrichment_status") or "done"
            lead.lead_metadata = metadata or None
        await session.commit()

    return {"dispatched": len(leads)}


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    try:
        lead = await lead_service.create_lead(session, workspace, payload)
    except DuplicateLeadError as exc:
        raise _duplicate_error(exc.field) from exc
    try:
        score_lead_task.delay(lead.id)
    except Exception as exc:
        # Scoring is a background nice-to-have (score stays None, an already
        # supported state) -- a queuing failure must never take down lead
        # creation itself.
        logger.warning("Could not dispatch scoring for lead %s: %s", lead.id, exc)
    return lead_to_read(lead)


@router.get("/{lead_id}", response_model=LeadRead)
async def get_lead(
    lead_id: str,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    lead = await lead_service.get_lead(session, workspace.id, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead_to_read(lead)


@router.patch("/{lead_id}", response_model=LeadRead)
async def update_lead(
    lead_id: str,
    payload: LeadUpdate,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    try:
        lead = await lead_service.update_lead(session, workspace.id, lead_id, payload)
    except DuplicateLeadError as exc:
        raise _duplicate_error(exc.field) from exc
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead_to_read(lead)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: str,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    deleted = await lead_service.delete_lead(session, workspace.id, lead_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")


@router.post("/{lead_id}/email", response_model=LeadEmailResponse)
async def send_lead_email(
    lead_id: str,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    try:
        await lead_service.send_lead_email(session, workspace, lead_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return LeadEmailResponse(sent=True)


@router.post("/{lead_id}/whatsapp", response_model=LeadWhatsAppResponse)
async def send_lead_whatsapp(
    lead_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    _, url = await lead_service.record_whatsapp_outreach(session, workspace, lead_id)
    return LeadWhatsAppResponse(url=url)
