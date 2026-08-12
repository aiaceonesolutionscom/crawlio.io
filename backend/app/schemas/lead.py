from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class LeadCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    industry: Optional[str] = None
    source: Optional[str] = None
    social_links: Optional[dict[str, str]] = None
    lead_metadata: Optional[dict[str, Any]] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    industry: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    social_links: Optional[dict[str, str]] = None


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    address: Optional[str]
    lat: Optional[float] = None
    lon: Optional[float] = None
    industry: Optional[str]
    score: Optional[int]
    status: str
    source: Optional[str]
    scoring_failed: bool = False
    social_links: dict[str, str] = Field(default_factory=dict)
    completeness: Optional[int] = None
    enrichment_status: Optional[str] = None
    enrichment_source: Optional[str] = None
    last_enriched_at: Optional[str] = None
    description: Optional[str] = None
    hours: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadRead]
    total: int
    page: int
    limit: int


class LeadEnrichRequest(BaseModel):
    lead_ids: list[str]


class LeadEnrichDispatchResult(BaseModel):
    dispatched: int


class LeadEmailResponse(BaseModel):
    sent: bool


class LeadWhatsAppResponse(BaseModel):
    url: str


def lead_to_read(lead) -> LeadRead:
    metadata = lead.lead_metadata or {}
    return LeadRead(
        id=lead.id,
        workspace_id=lead.workspace_id,
        name=lead.name,
        email=lead.email,
        phone=lead.phone,
        website=lead.website,
        address=lead.address,
        lat=lead.lat,
        lon=lead.lon,
        industry=lead.industry,
        score=lead.score,
        status=lead.status,
        source=lead.source,
        scoring_failed=bool(metadata.get("scoring_failed")),
        social_links=metadata.get("social_links") or {},
        completeness=metadata.get("completeness"),
        enrichment_status=metadata.get("enrichment_status"),
        enrichment_source=metadata.get("enrichment_source"),
        last_enriched_at=metadata.get("last_enriched_at"),
        description=metadata.get("description"),
        hours=metadata.get("hours"),
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )
