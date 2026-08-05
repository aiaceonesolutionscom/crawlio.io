from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

TeamRole = Literal["Owner", "Admin", "Member"]
TeamEntryStatus = Literal["Active", "Invited"]


class InviteMemberCreate(BaseModel):
    email: str
    role: TeamRole = "Member"


class TeamEntryRead(BaseModel):
    id: str
    name: Optional[str]
    email: Optional[str]
    role: TeamRole
    status: TeamEntryStatus
    created_at: datetime


class TeamListResponse(BaseModel):
    items: list[TeamEntryRead]
    seats_used: int
    seat_quota: int
