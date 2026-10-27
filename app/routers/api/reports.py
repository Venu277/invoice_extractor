from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.services.profit_loss_service import compute_profit_and_loss
from app.services.report_pdf_service import generate_monthly_report_pdf

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/profit-and-loss")
def get_pnl(
    fy: int | None = None,
    quarter: str | None = None,
    month: str | None = None,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    return compute_profit_and_loss(
        db=db,
        business_id=current_user.business_id,
        fy=fy,
        quarter=quarter,
        month=month
    )


@router.get("/monthly-pdf")
def download_monthly_pdf(
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    pdf_bytes = generate_monthly_report_pdf(db, current_user.business_id, month)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Monthly_Report_{month}.pdf"'}
    )
