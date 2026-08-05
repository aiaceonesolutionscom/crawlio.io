from pydantic import BaseModel


class WeekBucket(BaseModel):
    week: str
    leads: int
    qualified: int


class SourceSlice(BaseModel):
    name: str
    value: int


class StatusCount(BaseModel):
    status: str
    count: int


class AnalyticsOverview(BaseModel):
    total_leads: int
    qualified_leads: int
    avg_score: float
    leads_over_time: list[WeekBucket]
    source_split: list[SourceSlice]
    status_breakdown: list[StatusCount]
