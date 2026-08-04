from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class LeadCreate(BaseModel):
    name: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    lead_metadata: Optional[dict[str, Any]] = None


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    company: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    score: Optional[int]
    status: str
    source: Optional[str]
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadRead]
    total: int
