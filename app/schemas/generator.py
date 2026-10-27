from datetime import date
from pydantic import BaseModel, Field


class GeneratorItem(BaseModel):
    description: str = Field(..., min_length=1)
    hsn_sac: str | None = None
    quantity: float = Field(..., gt=0)
    unit: str = "NOS"
    rate_paise: int = Field(..., ge=0)
    gst_rate: float = Field(18.0, ge=0)


class GenerateInvoiceRequest(BaseModel):
    customer_id: int
    invoice_date: date = Field(default_factory=date.today)
    items: list[GeneratorItem] = Field(..., min_length=1)
    notes: str | None = None


class RecurringTemplateCreate(BaseModel):
    party_id: int
    items: list[GeneratorItem]
    frequency: str = Field("monthly", pattern="^(weekly|monthly|quarterly|yearly)$")
    start_date: date = Field(default_factory=date.today)
    end_date: date | None = None


class ShareLinkResponse(BaseModel):
    id: int
    kind: str
    ref: str
    token: str
    share_url: str
    whatsapp_url: str
    expires_at: str
    revoked: bool
