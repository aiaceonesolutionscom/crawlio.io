from typing import Optional

from pydantic import BaseModel

from app.schemas.lead import LeadRead


class DiscoverRequest(BaseModel):
    niche: str
    country: str  # ISO 3166-1 alpha-2 code, e.g. "PK"
    city: str
    lat: float
    lon: float
    limit: Optional[int] = None  # how many results the user wants; capped server-side by plan


class DiscoveredLead(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    industry: Optional[str] = None
    social_links: dict[str, str] = {}
    source: str = "openstreetmap"


class DiscoverResponse(BaseModel):
    items: list[DiscoveredLead]
    total: int
    limit: int
    enhanced: bool = False
    daily_limit: int
    remaining_today: int


class DiscoveryImportRequest(BaseModel):
    items: list[DiscoveredLead]


class DiscoveryImportSkip(BaseModel):
    name: str
    reason: str


class DiscoveryImportResult(BaseModel):
    created: list[LeadRead]
    skipped: list[DiscoveryImportSkip]
