from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.workspace import PlanId


class PlatformAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    clerk_user_id: Optional[str]
    added_by: Optional[str]
    is_active: bool
    created_at: datetime
    revoked_at: Optional[datetime]


class PlatformAdminCreate(BaseModel):
    email: str


class WhoamiRead(BaseModel):
    email: str
    is_super_admin: bool = True


class PlanConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan_key: str
    display_name: str
    lead_quota: int
    seat_quota: int
    discovery_result_limit: int
    daily_discovery_import_limit: int
    daily_email_limit: int
    capabilities: list[str]
    sort_order: int
    is_active: bool
    updated_at: datetime


class PlanConfigUpdate(BaseModel):
    display_name: Optional[str] = None
    lead_quota: Optional[int] = None
    seat_quota: Optional[int] = None
    discovery_result_limit: Optional[int] = None
    daily_discovery_import_limit: Optional[int] = None
    daily_email_limit: Optional[int] = None
    capabilities: Optional[list[str]] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class AdminWorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    plan: str
    lead_quota: int
    seat_quota: int
    webhook_token: str
    created_at: datetime


class AdminWorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    plan: Optional[PlanId] = None
    lead_quota: Optional[int] = None
    seat_quota: Optional[int] = None


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_email: str
    action: str
    target_type: str
    target_id: Optional[str]
    workspace_id: Optional[str]
    before: Optional[dict]
    after: Optional[dict]
    created_at: datetime


class FeatureFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    key: str
    description: Optional[str]
    default_enabled: bool
    created_at: datetime
    updated_at: datetime


class FeatureFlagCreate(BaseModel):
    key: str
    description: Optional[str] = None
    default_enabled: bool = False


class FeatureFlagUpdate(BaseModel):
    description: Optional[str] = None
    default_enabled: Optional[bool] = None


class FeatureFlagOverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    flag_id: str
    workspace_id: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class FeatureFlagOverrideSet(BaseModel):
    workspace_id: str
    is_enabled: bool


class SystemSettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    key: str
    value: Optional[Any]
    value_type: str
    description: Optional[str]
    updated_by: Optional[str]
    updated_at: datetime


class SystemSettingUpsert(BaseModel):
    value: Any
    value_type: str = "string"
    description: Optional[str] = None


class PlanCount(BaseModel):
    plan: str
    count: int


class WeekCount(BaseModel):
    week: str
    count: int


class AdminDashboardOverview(BaseModel):
    total_workspaces: int
    workspaces_by_plan: list[PlanCount]
    total_leads: int
    new_workspaces_over_time: list[WeekCount]
    active_platform_admins: int
