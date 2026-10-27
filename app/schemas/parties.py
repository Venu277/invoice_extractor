from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class PartyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    gstin: str | None = Field(None, max_length=15)
    state_code: str | None = Field(None, max_length=2)
    type: str = Field("vendor", pattern="^(vendor|customer|both)$")
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    payment_terms_days: int | None = 30
    credit_limit_paise: int = 0


class PartyCreate(PartyBase):
    pass


class PartyUpdate(BaseModel):
    name: str | None = None
    gstin: str | None = None
    state_code: str | None = None
    type: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    payment_terms_days: int | None = None
    credit_limit_paise: int | None = None


class PartyResponse(PartyBase):
    id: int
    business_id: int
    auto_created: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
