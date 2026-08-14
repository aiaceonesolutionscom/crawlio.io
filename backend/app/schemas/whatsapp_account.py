from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WhatsAppAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    user_id: str
    phone_number_id: str
    waba_id: Optional[str] = None
    business_phone: Optional[str] = None
    display_name: Optional[str] = None
    token_type: str
    is_active: bool
    daily_sent_count: int
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class WhatsAppAccountListResponse(BaseModel):
    items: list[WhatsAppAccountRead]


class WhatsAppConnectResponse(BaseModel):
    auth_url: Optional[str] = None
    test_mode: bool = False


class WhatsAppManualConnectRequest(BaseModel):
    phone_number_id: str
    access_token: str
    waba_id: Optional[str] = None
    business_phone: Optional[str] = None
    display_name: Optional[str] = None


class WhatsAppQuotaRead(BaseModel):
    sent_count: int
    limit: int
    remaining: int
