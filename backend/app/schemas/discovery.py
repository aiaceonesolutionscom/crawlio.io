from typing import Optional

from pydantic import BaseModel

from app.schemas.lead import LeadRead


class DiscoverRequest(BaseModel):
    niche: str
    country: str  # ISO 3166-1 alpha-2 code, e.g. "PK"
    city: str
    # Kept for API backwards-compatibility with existing frontends that send
    # coordinates — discovery is web-based now (Tavily + DuckDuckGo), so these
    # are accepted and ignored.
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
    source: str = "web_search"
    enrichment_status: Optional[str] = None
    enrichment_error: Optional[str] = None
    hours: Optional[str] = None
    description: Optional[str] = None
    completeness: Optional[int] = None
    last_enriched_at: Optional[str] = None
    enrichment_source: Optional[str] = None


class DiscoverResponse(BaseModel):
    items: list[DiscoveredLead]
    total: int
    limit: int
    enhanced: bool = False
    daily_limit: int
    remaining_today: int
    search_id: Optional[str] = None


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
