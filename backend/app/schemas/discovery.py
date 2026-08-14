from typing import Optional

from pydantic import BaseModel

from app.schemas.lead import LeadRead


class DiscoverRequest(BaseModel):
    niche: str
    country: str  # ISO 3166-1 alpha-2 code, e.g. "PK"
    city: str
    # Kept for API backwards-compatibility with existing frontends that send
    # coordinates — discovery crawls by name, so these are accepted and ignored.
    lat: Optional[float] = None
    lon: Optional[float] = None
    limit: Optional[int] = None  # how many results the user wants; capped server-side by plan


class DiscoveredLead(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    industry: Optional[str] = None
    social_links: dict[str, str] = {}
    source: str = "google_maps"
    enrichment_status: Optional[str] = None
    enrichment_error: Optional[str] = None
    hours: Optional[str] = None
    description: Optional[str] = None
    completeness: Optional[int] = None
    last_enriched_at: Optional[str] = None
    enrichment_source: Optional[str] = None
    # Apify-style enrichment from Google Maps.
    rating: Optional[float] = None
    review_count: Optional[int] = None
    category: Optional[str] = None
    plus_code: Optional[str] = None
    # Cache/geo-fallback transparency — additive, defaults preserve old behavior.
    cache_hit: bool = False
    cached_at: Optional[str] = None
    result_city: Optional[str] = None
    is_fallback_city: bool = False
    # True when this business (by email/phone) already exists as a Lead in the
    # requesting workspace's CRM — lets a repeat search show what's actually
    # new instead of looking like a frozen re-run of the same list.
    already_in_workspace: bool = False


class DiscoverResponse(BaseModel):
    items: list[DiscoveredLead]
    total: int
    limit: int
    enhanced: bool = False
    daily_limit: int
    remaining_today: int
    search_id: Optional[str] = None
    # Raw per-source candidate counts before validation — diagnostics so the
    # frontend can show why a search came up short (e.g. "Maps 0 · OSM 12").
    source_counts: dict[str, int] = {}


class DiscoveryStatusResponse(BaseModel):
    search_id: str
    status: str
    items: list[DiscoveredLead]


class DiscoveryImportRequest(BaseModel):
    items: list[DiscoveredLead]


class DiscoveryImportSkip(BaseModel):
    name: str
    reason: str


class DiscoveryImportResult(BaseModel):
    created: list[LeadRead]
    skipped: list[DiscoveryImportSkip]
