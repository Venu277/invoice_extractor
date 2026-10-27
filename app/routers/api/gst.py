from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.gst.summaries import compute_gstr1_summary, compute_gstr3b_summary, compute_hsn_summary

router = APIRouter(prefix="/gst", tags=["GST Summaries"])


@router.get("/gstr1")
def get_gstr1(
    fy: int | None = None,
    month: str | None = Query(None, description="Month in YYYY-MM format"),
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    return compute_gstr1_summary(
        db=db,
        business_id=current_user.business_id,
        fy=fy,
        month=month
    )


@router.get("/gstr3b")
def get_gstr3b(
    fy: int | None = None,
    month: str | None = Query(None, description="Month in YYYY-MM format"),
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    return compute_gstr3b_summary(
        db=db,
        business_id=current_user.business_id,
        fy=fy,
        month=month
    )


@router.get("/hsn")
def get_hsn(
    fy: int | None = None,
    month: str | None = Query(None, description="Month in YYYY-MM format"),
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    return compute_hsn_summary(
        db=db,
        business_id=current_user.business_id,
        fy=fy,
        month=month
    )
