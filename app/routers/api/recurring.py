from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.models.recurring import RecurringTemplate
from app.schemas.generator import RecurringTemplateCreate
from app.schemas.invoices import InvoiceResponse
from app.services.recurring_service import create_recurring_template, process_due_recurring_invoices

router = APIRouter(prefix="/recurring", tags=["Recurring Invoices"])


@router.post("", status_code=status.HTTP_201_CREATED)
def add_template(
    data: RecurringTemplateCreate,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    tmpl = create_recurring_template(db, current_user.business_id, data)
    return {"message": "Recurring template created", "id": tmpl.id}


@router.get("")
def list_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return (
        db.query(RecurringTemplate)
        .filter(RecurringTemplate.business_id == current_user.business_id)
        .all()
    )


@router.post("/process", response_model=list[InvoiceResponse])
def trigger_recurring_processing(
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    invoices = process_due_recurring_invoices(db)
    return invoices
