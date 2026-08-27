from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

BillingProvider = Literal["stripe", "safepay"]
BillingCycleLiteral = Literal["monthly", "yearly"]


class CheckoutRequest(BaseModel):
    plan: Literal["pro"] = "pro"
    billing_cycle: BillingCycleLiteral
    provider: BillingProvider


class CheckoutResponse(BaseModel):
    checkout_url: str
    provider: BillingProvider


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: BillingProvider
    plan: str
    billing_cycle: BillingCycleLiteral
    status: str
    current_period_end: Optional[datetime]
    canceled_at: Optional[datetime]
    created_at: datetime
