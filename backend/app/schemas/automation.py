from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SequenceStatus = Literal["draft", "active", "paused"]


class SequenceStepCreate(BaseModel):
    subject: str
    body: str
    delay_hours: int = Field(default=0, ge=0)


class SequenceStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    step_order: int
    delay_hours: int
    subject: str
    body: str


class SequenceCreate(BaseModel):
    name: str
    trigger: str = "lead_created"
    steps: list[SequenceStepCreate] = []


class SequenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    trigger: str
    status: SequenceStatus
    created_at: datetime
    steps: list[SequenceStepRead]


class SequenceListResponse(BaseModel):
    items: list[SequenceRead]


class SequenceStatusUpdate(BaseModel):
    status: SequenceStatus


class InboundLeadCapture(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = "webhook"
