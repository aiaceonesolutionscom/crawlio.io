from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class LeadCreate(BaseModel):
    name: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    source: Optional[str] = None
    lead_metadata: Optional[dict[str, Any]] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    company: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    address: Optional[str]
    score: Optional[int]
    status: str
    source: Optional[str]
    scoring_failed: bool = False
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadRead]
    total: int
    page: int
    limit: int


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
        company=lead.company,
        email=lead.email,
        phone=lead.phone,
        website=lead.website,
        address=lead.address,
        score=lead.score,
        status=lead.status,
        source=lead.source,
        scoring_failed=bool(metadata.get("scoring_failed")),
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )
