import asyncio
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
    LeadEnrichRequest,
    LeadEnrichResult,
    LeadListResponse,
    LeadRead,
    LeadUpdate,
    LeadWhatsAppResponse,
    lead_to_read,
)
from app.services import browser_scraper_service, crm_service, lead_service, tavily_service, website_scraper_service
from app.services.lead_service import DuplicateLeadError
from app.workers.tasks_scoring import score_lead_task

router = APIRouter(prefix="/leads", tags=["leads"])

# How many selected leads get a per-lead enrichment pass in one request —
# bounded so a large bulk selection can't turn into dozens of concurrent
# outbound HTTP calls (website fetches, and Tavily searches for Pro+).
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


@router.post("/enrich", response_model=LeadEnrichResult)
async def enrich_leads(
    payload: LeadEnrichRequest,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Re-run contact enrichment on leads that already exist — useful for
    leads that were added manually, imported incomplete, or missed contact
    info the first time. Never overwrites data that's already there, only
    fills gaps."""
    lead_ids = payload.lead_ids[:MAX_ENRICH_PER_REQUEST]
    leads = await lead_service.get_leads_by_ids(session, workspace.id, lead_ids)
    enhanced = "lead_discovery_enhanced" in PLAN_CAPABILITIES.get(workspace.plan, set())

    # Websites found for this batch, keyed by lead id — a lead without a
    # website yet gets one from Tavily (Pro+ only), then every lead with a
    # website (original or freshly found) gets scraped for contact details.
    found_websites: dict[str, str] = {}
    if enhanced:
        missing_website_leads = [lead for lead in leads if not lead.website]
        if missing_website_leads:
            url_lookups = await asyncio.gather(
                *(
                    tavily_service.find_website_url(lead.name, lead.address or "", "")
                    for lead in missing_website_leads
                ),
                return_exceptions=True,
            )
            for lead, url in zip(missing_website_leads, url_lookups):
                if isinstance(url, str) and url:
                    found_websites[lead.id] = url

    scrapable = [lead for lead in leads if lead.website or lead.id in found_websites]
    urls = [lead.website or found_websites[lead.id] for lead in scrapable]

    if enhanced:
        # A real headless-browser scrape (renders JS, follows /contact &
        # /about) — the fuller extraction Pro's "total data" promise is built on.
        scraped = await browser_scraper_service.extract_contact_details(urls)
    else:
        scraped = await asyncio.gather(
            *(website_scraper_service.extract_contact_from_website(url) for url in urls),
            return_exceptions=True,
        )

    found_by_lead_id: dict[str, dict] = {}
    for lead, found in zip(scrapable, scraped):
        if isinstance(found, dict):
            found_by_lead_id[lead.id] = dict(found)

    for lead_id, website in found_websites.items():
        found_by_lead_id.setdefault(lead_id, {})["website"] = website

    enriched_count = 0
    for lead in leads:
        found = found_by_lead_id.get(lead.id, {})
        if found and lead_service.apply_enrichment_to_lead(lead, found):
            enriched_count += 1
    await session.commit()

    return LeadEnrichResult(enriched=enriched_count, unchanged=len(leads) - enriched_count)


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
    score_lead_task.delay(lead.id)
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
