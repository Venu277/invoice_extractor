from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class InvoiceItemBase(BaseModel):
    description: str = Field(..., min_length=1)
    hsn_sac: str | None = None
    quantity: float = 1.0
    unit: str | None = "NOS"
    rate: int = 0  # paise
    taxable: int = 0  # paise
    gst_rate: float = 18.0
    cgst: int = 0  # paise
    sgst: int = 0  # paise
    igst: int = 0  # paise
    amount: int = 0  # paise


class InvoiceItemCreate(InvoiceItemBase):
    pass


class InvoiceItemResponse(InvoiceItemBase):
    id: int
    invoice_id: int

    model_config = ConfigDict(from_attributes=True)


class InvoiceUpdate(BaseModel):
    direction: str | None = None
    invoice_no: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    party_id: int | None = None
    supplier_gstin: str | None = None
    buyer_gstin: str | None = None
    place_of_supply_state: str | None = None
    taxable: int | None = None
    cgst: int | None = None
    sgst: int | None = None
    igst: int | None = None
    cess: int | None = None
    total: int | None = None
    items: list[InvoiceItemCreate] | None = None


class InvoiceResponse(BaseModel):
    id: int
    business_id: int
    party_id: int | None
    document_id: int | None
    direction: str
    source: str
    invoice_no: str
    invoice_date: date | None
    due_date: date | None
    supplier_gstin: str | None
    buyer_gstin: str | None
    place_of_supply_state: str | None

    taxable: int
    cgst: int
    sgst: int
    igst: int
    cess: int
    total: int
    amount_paid: int

    payment_status: str
    review_status: str
    validation_status: str
    validation_issues: list[dict[str, Any]] | None
    field_confidence: dict[str, Any] | None

    created_by: int | None
    approved_by: int | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    items: list[InvoiceItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class BatchResponse(BaseModel):
    id: int
    business_id: int
    total: int
    done: int
    failed: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
