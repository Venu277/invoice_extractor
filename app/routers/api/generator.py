from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.generator import GenerateInvoiceRequest
from app.schemas.invoices import InvoiceResponse
from app.services.invoice_generator_service import generate_sales_invoice, generate_sales_invoice_pdf

router = APIRouter(prefix="/generator", tags=["Invoice Generator"])


@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_sales_invoice(
    req: GenerateInvoiceRequest,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    inv = generate_sales_invoice(db, current_user.business_id, current_user.id, req)
    return inv


@router.get("/invoices/{invoice_id}/pdf")
def download_sales_invoice_pdf(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pdf_bytes = generate_sales_invoice_pdf(db, current_user.business_id, invoice_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Invoice_{invoice_id}.pdf"'}
    )
