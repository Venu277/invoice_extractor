from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.payments import AgeingReportResponse
from app.services.ageing_service import compute_ageing_report

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/ageing", response_model=AgeingReportResponse)
def get_ageing_report(
    direction: str = Query("sales", pattern="^(sales|purchase)$"),
    as_of: date | None = None,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    return compute_ageing_report(
        db=db,
        business_id=current_user.business_id,
        direction=direction,
        as_of=as_of
    )
