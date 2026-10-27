from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.models.document import ImportBatch, Document
from app.schemas.invoices import BatchResponse
from app.services.document_service import handle_file_upload

router = APIRouter(prefix="/documents", tags=["Documents & Upload"])


@router.post("/upload", response_model=BatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_invoices(
    files: list[UploadFile] = File(...),
    sync: bool = False,
    current_user: User = Depends(require_role("owner", "accountant", "staff")),
    db: Session = Depends(get_db)
):
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided."
        )

    files_data = []
    for f in files:
        content = await f.read()
        files_data.append((f.filename or "upload.pdf", content))

    batch = handle_file_upload(
        db=db,
        business_id=current_user.business_id,
        user_id=current_user.id,
        files_data=files_data,
        sync=sync
    )
    return batch


@router.get("/batches/{batch_id}", response_model=BatchResponse)
def get_batch_progress(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batch = db.query(ImportBatch).filter(
        ImportBatch.id == batch_id,
        ImportBatch.business_id == current_user.business_id
    ).first()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import batch not found."
        )
    return batch


@router.get("/{document_id}/file")
def get_document_pdf(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.business_id == current_user.business_id
    ).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )

    file_path = Path(doc.stored_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Underlying PDF file missing on disk."
        )

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=doc.original_name
    )
