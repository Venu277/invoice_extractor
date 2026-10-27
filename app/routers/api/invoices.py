from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.invoices import InvoiceResponse, InvoiceUpdate
from app.services.invoice_service import (
    list_invoices,
    get_invoice,
    update_and_validate_invoice,
    approve_invoice,
    reject_invoice,
    delete_invoice
)

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("", response_model=list[InvoiceResponse])
def get_invoices_list(
    direction: str | None = None,
    review_status: str | None = None,
    payment_status: str | None = None,
    party_id: int | None = None,
    month: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    invoices, _ = list_invoices(
        db=db,
        business_id=current_user.business_id,
        direction=direction,
        review_status=review_status,
        payment_status=payment_status,
        party_id=party_id,
        month=month,
        page=page,
        page_size=page_size
    )
    return invoices


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice_detail(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_invoice(db, current_user.business_id, invoice_id)


@router.put("/{invoice_id}", response_model=InvoiceResponse)
def edit_invoice(
    invoice_id: int,
    data: InvoiceUpdate,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    return update_and_validate_invoice(db, current_user.business_id, invoice_id, data)


@router.post("/{invoice_id}/approve", response_model=InvoiceResponse)
def approve(
    invoice_id: int,
    direction: str | None = None,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    return approve_invoice(db, current_user.business_id, invoice_id, current_user, direction=direction)


@router.post("/{invoice_id}/reject", response_model=InvoiceResponse)
def reject(
    invoice_id: int,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    return reject_invoice(db, current_user.business_id, invoice_id, current_user)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    invoice_id: int,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    delete_invoice(db, current_user.business_id, invoice_id)
    return None
