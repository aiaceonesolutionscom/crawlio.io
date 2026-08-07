import asyncio
import logging
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, require_plan
from app.core.plans import DAILY_DISCOVERY_IMPORT_LIMITS, DISCOVERY_LIMITS, PLAN_CAPABILITIES
from app.data.niches import SUGGESTED_NICHES
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
from app.services import (
    browser_scraper_service,
    discovery_service,
    geo_service,
    listing_extraction_service,
    tavily_service,
    website_scraper_service,
)
from app.services.lead_service import DuplicateLeadError, create_lead
from app.services.quota_service import count_discovery_leads_today

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads/discover", tags=["lead-discovery"])

# How many results get a Tavily website-URL lookup per search (Pro+). Bounded
# to keep latency and API usage predictable — Tavily is a paid, rate-limited
# external call per lead.
MAX_TAVILY_ENRICHED_PER_SEARCH = 15
# Website-content scraping is free (no API, no per-call cost), so free tier can
# afford to enrich more candidates — this matters because free tier's strict
# "no blanks" filter drops anything scraping doesn't complete.
MAX_SCRAPED_PER_SEARCH = 60
# Pro+ only: real headless-browser scraping is far heavier per-site than a
# plain HTTP GET (page render, multiple subpath navigations), so this is kept
# well below the plain-HTTP cap to keep total search latency reasonable.
MAX_BROWSER_SCRAPED_PER_SEARCH = 25
# Free tier requires every field non-blank. In practice most OSM POIs don't
# even carry a website tag (observed as low as ~3% for some niche+city
# combinations), and without a website there's no free way to find an email —
# so the real ceiling on complete results is "how many raw OSM matches have a
# website tag," not the requested count. Over-fetching hard against that
# ceiling is the only lever available without a paid search API.
FREE_TIER_OVERFETCH_MULTIPLIER = 6
# Pro+ only: how many Tavily-returned directory/listicle pages get an LLM
# extraction pass per search. Each page is a separate Mistral call, so this
# bounds both latency and cost — 4 pages is enough headroom since a single
# good listicle (e.g. "50 best X in City") often yields a dozen+ businesses.
MAX_TAVILY_LISTING_PAGES = 4
TAVILY_LISTING_MIN_CONTENT_CHARS = 500


@router.get("/niches")
async def list_niche_suggestions(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    q: Optional[str] = Query(default=None),
):
    if not q:
        return {"items": SUGGESTED_NICHES}
    matches = [n for n in SUGGESTED_NICHES if q.lower() in n.lower()]
    return {"items": matches}


@router.post("", response_model=DiscoverResponse)
async def discover(
    payload: DiscoverRequest,
    workspace: Annotated[Workspace, Depends(require_plan("lead_discovery"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    plan_cap = DISCOVERY_LIMITS.get(workspace.plan, 50)
    limit = min(payload.limit, plan_cap) if payload.limit else plan_cap
    limit = max(limit, 1)

    enhanced = "lead_discovery_enhanced" in PLAN_CAPABILITIES.get(workspace.plan, set())
    # Free tier's strict filter (below) drops any OSM result enrichment can't
    # fully complete, so ask OSM for more than `limit` up front.
    fetch_limit = limit if enhanced else min(limit * FREE_TIER_OVERFETCH_MULTIPLIER, 200)

    try:
        results = await discovery_service.discover_businesses(
            payload.niche, payload.lat, payload.lon, payload.city, limit=fetch_limit
        )
    except discovery_service.DiscoveryUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    country_name = geo_service.country_name_for_code(payload.country) or payload.country

    if enhanced:
        # Paid tier: on top of OSM, search directory/listicle pages (Yellow
        # Pages, Yelp, local "best of" lists) via Tavily and extract individual
        # businesses out of them with an LLM pass. This finds businesses OSM
        # has no record of at all, not just fields OSM left blank.
        web_results = await _discover_via_tavily(payload.niche, payload.city, country_name, fetch_limit)
        results = _merge_discovery_results(results, web_results)

        # Tavily's only remaining job here is finding a website URL for
        # results that don't have one yet — search snippets are too shallow
        # for reliable contact details, so that's left entirely to the
        # headless-browser scrape below, which reads the site itself.
        results = await _find_missing_websites(results, payload.city, country_name)

        # Real headless-browser scrape (renders JS, follows /contact & /about)
        # for email/phone/social — the fuller extraction Pro's "total data"
        # promise is built on.
        results = await _enrich_from_own_websites(
            results, cap=MAX_BROWSER_SCRAPED_PER_SEARCH, use_browser=True
        )
    else:
        # Free tier: plain-HTTP scrape of the business's own page (and
        # /contact, /about) — no API key, no rate limits, just GETs to pages
        # the business itself publishes.
        results = await _enrich_from_own_websites(results, cap=MAX_SCRAPED_PER_SEARCH, use_browser=False)

        # Every shown lead must have name, website, phone, email and industry
        # — no blanks. Industry is always set (derived from the searched
        # niche), so this is really "did enrichment fill in the rest."
        results = [r for r in results if r.get("website") and r.get("phone") and r.get("email")]

    # Most-complete-first: results with real contact info are more useful leads
    # than a bare name+address, especially once the user is picking a subset
    # within their daily add limit.
    results.sort(key=lambda r: sum(bool(r.get(f)) for f in ("phone", "email", "website")), reverse=True)
    results = results[:limit]

    daily_limit = DAILY_DISCOVERY_IMPORT_LIMITS.get(workspace.plan, 50)
    used_today = await count_discovery_leads_today(session, workspace.id)
    remaining_today = max(daily_limit - used_today, 0)

    items = [DiscoveredLead(**r) for r in results]
    return DiscoverResponse(
        items=items, total=len(items), limit=limit, enhanced=enhanced,
        daily_limit=daily_limit, remaining_today=remaining_today,
    )


def _discovery_dedup_key(result: dict) -> tuple:
    return (
        result["name"].strip().lower(),
        (result.get("phone") or "").strip(),
        (result.get("website") or "").strip(),
    )


def _merge_discovery_results(primary: list[dict], extra: list[dict]) -> list[dict]:
    seen = {_discovery_dedup_key(r) for r in primary}
    merged = list(primary)
    for item in extra:
        key = _discovery_dedup_key(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


async def _discover_via_tavily(niche: str, city: str, country_name: str, limit: int) -> list[dict]:
    try:
        pages = await tavily_service.discover_listing_pages(niche, city, country_name, max_results=6)
    except (httpx.HTTPError, RuntimeError) as exc:
        logger.warning("Tavily listing search failed for %s in %s: %s", niche, city, exc)
        return []

    candidate_pages = [
        p for p in pages if len(p.get("raw_content") or "") > TAVILY_LISTING_MIN_CONTENT_CHARS
    ][:MAX_TAVILY_LISTING_PAGES]
    if not candidate_pages:
        return []

    per_page_limit = max(5, limit // len(candidate_pages))
    extractions = await asyncio.gather(
        *(
            listing_extraction_service.extract_businesses(niche, city, page["raw_content"], max_items=per_page_limit)
            for page in candidate_pages
        ),
        return_exceptions=True,
    )

    collected: list[dict] = []
    seen: set[tuple] = set()
    for items in extractions:
        if not isinstance(items, list):
            continue
        for item in items:
            key = _discovery_dedup_key(item)
            if key in seen:
                continue
            seen.add(key)
            collected.append({
                **item,
                "address": item.get("address") or city,
                "industry": niche.strip().title(),
                "social_links": {},
                "source": "web_search",
            })
            if len(collected) >= limit:
                return collected
    return collected


async def _enrich_from_own_websites(
    results: list[dict], cap: int = MAX_SCRAPED_PER_SEARCH, use_browser: bool = False
) -> list[dict]:
    to_enrich = [
        r for r in results
        if r.get("website") and not (r.get("email") and r.get("phone") and r.get("social_links"))
    ]
    to_enrich = to_enrich[:cap]
    if not to_enrich:
        return results

    if use_browser:
        lookups = await browser_scraper_service.extract_contact_details([r["website"] for r in to_enrich])
    else:
        lookups = await asyncio.gather(
            *(website_scraper_service.extract_contact_from_website(r["website"]) for r in to_enrich),
            return_exceptions=True,
        )

    for result, found in zip(to_enrich, lookups):
        if isinstance(found, dict):
            for field in ("email", "phone"):
                if not result.get(field) and found.get(field):
                    result[field] = found[field]
            if found.get("social_links"):
                result["social_links"] = {**found["social_links"], **result.get("social_links", {})}
    return results


async def _find_missing_websites(results: list[dict], city: str, country_name: str) -> list[dict]:
    to_search = [r for r in results if not r.get("website")]
    to_search = to_search[:MAX_TAVILY_ENRICHED_PER_SEARCH]
    if not to_search:
        return results

    found_urls = await asyncio.gather(
        *(tavily_service.find_website_url(r["name"], city, country_name) for r in to_search),
        return_exceptions=True,
    )
    for result, url in zip(to_search, found_urls):
        if isinstance(url, str) and url:
            result["website"] = url
    return results


@router.post("/import", response_model=DiscoveryImportResult)
async def import_discovered(
    payload: DiscoveryImportRequest,
    workspace: Annotated[Workspace, Depends(require_plan("lead_discovery"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    daily_limit = DAILY_DISCOVERY_IMPORT_LIMITS.get(workspace.plan, 50)
    used_today = await count_discovery_leads_today(session, workspace.id)

    created = []
    skipped = []

    for item in payload.items:
        if used_today + len(created) >= daily_limit:
            skipped.append(DiscoveryImportSkip(name=item.name, reason="daily_limit_reached"))
            continue
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
                    industry=item.industry,
                    social_links=item.social_links or None,
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
