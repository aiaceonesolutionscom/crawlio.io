from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

PlanId = Literal["free", "pro", "enterprise"]


class WorkspaceCreate(BaseModel):
    name: str
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    plan: PlanId
    plan_selected: bool
    lead_quota: int
    seat_quota: int
    leads_used: int
    seats_used: int
    created_at: datetime


class WorkspacePlanUpdate(BaseModel):
    plan: PlanId
