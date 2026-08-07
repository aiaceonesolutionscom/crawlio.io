from datetime import datetime

from pydantic import BaseModel

from app.schemas.lead import LeadRead


class AiFilterResponse(BaseModel):
    with_website: list[LeadRead]
    without_website: list[LeadRead]


class CrmAddRequest(BaseModel):
    lead_ids: list[str]


class CrmAddResult(BaseModel):
    added: int
    skipped: int


class CrmEntryRead(BaseModel):
    id: str
    lead: LeadRead
    category: str
    added_at: datetime


class CrmEntryListResponse(BaseModel):
    items: list[CrmEntryRead]
    total: int
