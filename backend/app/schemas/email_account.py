from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class EmailAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    user_id: str
    email_address: str
    display_name: Optional[str] = None
    provider: str
    is_active: bool
    daily_sent_count: int
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class EmailAccountListResponse(BaseModel):
    items: list[EmailAccountRead]


class EmailAccountConnectResponse(BaseModel):
    auth_url: str


class EmailDraftCreate(BaseModel):
    email_account_id: str
    subject: str
    body: str
    kind: str = "composed"
    recipient_emails: Optional[list[str]] = None
    lead_id: Optional[str] = None
    ai_prompt: Optional[str] = None
    conversation_id: Optional[str] = None


class EmailDraftUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    recipient_emails: Optional[list[str]] = None


class EmailDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    email_account_id: str
    lead_id: Optional[str] = None
    subject: str
    body: str
    kind: str
    status: str
    recipient_emails: Optional[str] = None
    ai_prompt: Optional[str] = None
    conversation_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EmailDraftListResponse(BaseModel):
    items: list[EmailDraftRead]


class EmailQuotaRead(BaseModel):
    composed_count: int
    ai_generated_count: int
    total_sent: int
    limit: int
    remaining: int


class EmailConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    email_account_id: str
    lead_id: Optional[str] = None
    subject: str
    status: str
    ai_agent_active: bool
    business_context: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EmailConversationMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sender_type: str
    content: str
    is_approved: bool
    sent_at: Optional[datetime] = None
    created_at: datetime


class EmailAgentInitializeRequest(BaseModel):
    email_account_id: str
    lead_id: Optional[str] = None
    subject: str = "Outreach Conversation"


class EmailAgentMessageRequest(BaseModel):
    conversation_id: str
    message: str


class EmailAIGenerateRequest(BaseModel):
    email_account_id: str
    prompt: str
    lead_id: Optional[str] = None
    lead_name: str = ""
    lead_company: str = ""
    lead_email: str = ""


class EmailMessageRead(BaseModel):
    id: str
    thread_id: Optional[str] = None
    subject: str
    from_email: str = ""
    to_email: str = ""
    date: str
    body: str = ""
    body_preview: str = ""
    snippet: str = ""
    label_ids: list[str] = []
    is_read: bool = True

    class Config:
        populate_by_name = True

    def __init__(self, **data):
        if "from" in data:
            data["from_email"] = data.pop("from")
        if "to" in data:
            data["to_email"] = data.pop("to")
        super().__init__(**data)


class EmailMessageListResponse(BaseModel):
    items: list[EmailMessageRead]
