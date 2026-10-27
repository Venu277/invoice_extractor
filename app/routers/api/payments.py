from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.payments import PaymentCreate, PaymentResponse, PartyLedgerResponse
from app.services.payment_service import record_payment, list_invoice_payments, get_party_ledger

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def make_payment(
    data: PaymentCreate,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    payment, _ = record_payment(db, current_user.business_id, current_user.id, data)
    return payment


@router.get("/invoice/{invoice_id}", response_model=list[PaymentResponse])
def get_invoice_payments(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return list_invoice_payments(db, current_user.business_id, invoice_id)


@router.get("/party/{party_id}/ledger", response_model=PartyLedgerResponse)
def get_ledger(
    party_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_party_ledger(db, current_user.business_id, party_id)
