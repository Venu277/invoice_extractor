from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.services.export_service import (
    export_invoices_csv,
    export_invoices_excel,
    export_tally_xml,
    export_accountant_package_zip
)

router = APIRouter(prefix="/exports", tags=["Exports & Accounting"])


@router.get("/csv")
def download_csv(
    fy: int | None = None,
    month: str | None = None,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    csv_str = export_invoices_csv(db, current_user.business_id, fy=fy, month=month)
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="invoices.csv"'}
    )


@router.get("/excel")
def download_excel(
    fy: int | None = None,
    month: str | None = None,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    xlsx_bytes = export_invoices_excel(db, current_user.business_id, fy=fy, month=month)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="invoices.xlsx"'}
    )


@router.get("/tally")
def download_tally(
    fy: int | None = None,
    month: str | None = None,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    xml_str = export_tally_xml(db, current_user.business_id, fy=fy, month=month)
    return Response(
        content=xml_str,
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="tally_vouchers.xml"'}
    )


@router.get("/accountant-package")
def download_accountant_package(
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    zip_bytes = export_accountant_package_zip(db, current_user.business_id, month=month)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="Accountant_Package_{month}.zip"'}
    )
