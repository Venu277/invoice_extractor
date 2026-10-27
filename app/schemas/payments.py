from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    invoice_id: int
    amount: int = Field(..., gt=0, description="Payment amount in integer paise")
    paid_on: date = Field(default_factory=date.today)
    method: str = Field("bank_transfer", pattern="^(upi|bank_transfer|cash|cheque|other)$")
    reference: str | None = None
    note: str | None = None


class PaymentResponse(BaseModel):
    id: int
    business_id: int
    invoice_id: int
    amount: int  # paise
    paid_on: date
    method: str
    reference: str | None
    note: str | None
    created_by: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartyLedgerEntry(BaseModel):
    date: date
    type: str  # invoice, payment
    reference_id: int
    reference_no: str | None
    description: str
    debit: int   # paise
    credit: int  # paise
    balance: int # running balance in paise


class PartyLedgerResponse(BaseModel):
    party_id: int
    party_name: str
    party_type: str
    total_debit: int
    total_credit: int
    current_balance: int
    entries: list[PartyLedgerEntry]


class AgeingBucket(BaseModel):
    not_due: int = 0
    days_1_30: int = 0
    days_31_60: int = 0
    days_61_90: int = 0
    days_90_plus: int = 0
    total_outstanding: int = 0


class PartyAgeingRow(BaseModel):
    party_id: int
    party_name: str
    buckets: AgeingBucket


class AgeingReportResponse(BaseModel):
    direction: str  # sales (receivables) or purchase (payables)
    as_of_date: date
    summary: AgeingBucket
    party_breakdown: list[PartyAgeingRow]
