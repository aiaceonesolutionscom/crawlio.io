from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WhatsAppConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    whatsapp_account_id: str
    lead_id: Optional[str] = None
    status: str
    ai_agent_active: bool
    business_context: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None
    last_processed_message_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class WhatsAppConversationMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sender_type: str
    content: str
    is_approved: bool
    sent_at: Optional[datetime] = None
    direction: str = "inbound"
    provider_message_id: Optional[str] = None
    created_at: datetime


class WhatsAppConversationListResponse(BaseModel):
    items: list[WhatsAppConversationRead]


class WhatsAppConversationPreviewRead(BaseModel):
    id: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    last_message: str = ""
    last_message_sender_type: str = ""
    last_message_at: Optional[datetime] = None
    ai_agent_active: bool = False
    status: str = "active"
    is_booked: bool = False
    business_context: Optional[str] = None


class WhatsAppConversationPreviewListResponse(BaseModel):
    items: list[WhatsAppConversationPreviewRead]
    page: int
    page_size: int
    has_more: bool
    total: int = 0


class WhatsAppConversationWithMessages(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    conversation: WhatsAppConversationRead
    messages: list[WhatsAppConversationMessageRead]


class WhatsAppConversationMessageRequest(BaseModel):
    conversation_id: str
    message: str
    sender_type: str = "user"


class WhatsAppBookingRequest(BaseModel):
    whatsapp_account_id: str
    conversation_id: Optional[str] = None
    lead_name: str
    lead_phone: str
    lead_company: str = ""
    meeting_datetime: str


class WhatsAppBusinessInfoRequest(BaseModel):
    whatsapp_account_id: str
    conversation_id: str
    business_name: str
    business_subject: str
    business_additional_info: str = ""


class WhatsAppStatsRead(BaseModel):
    outreach_sent_today: int
    inbound_received_today: int
    ai_replies_today: int
    meetings_booked_today: int
    active_conversations: int
    total_messages_today: int
