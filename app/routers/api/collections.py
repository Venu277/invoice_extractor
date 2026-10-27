from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.collection import InvoiceCollection
from app.models.invoice import Invoice

router = APIRouter(prefix="/collections", tags=["Invoice Collections"])


class CreateCollectionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000, le=2100)
    invoice_ids: list[int] = Field(default_factory=list)
    clear_workspace: bool = False


@router.post("", status_code=status.HTTP_201_CREATED)
def create_collection(
    req: CreateCollectionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    clean_name = req.name.strip()
    norm_name = clean_name.lower()

    if not clean_name:
        raise HTTPException(status_code=400, detail="Collection name cannot be empty.")

    # Enforce case-insensitive uniqueness rule
    existing = db.query(InvoiceCollection).filter(
        InvoiceCollection.business_id == user.business_id,
        InvoiceCollection.name_normalized == norm_name
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A collection named '{clean_name}' already exists. Collection names must be unique (case-insensitive)."
        )

    # If invoice_ids wasn't passed explicitly, collect current business invoices
    invoice_ids = req.invoice_ids
    if not invoice_ids:
        invoices = db.query(Invoice.id).filter(
            Invoice.business_id == user.business_id,
            Invoice.deleted_at.is_(None)
        ).all()
        invoice_ids = [inv[0] for inv in invoices]

    collection = InvoiceCollection(
        business_id=user.business_id,
        name=clean_name,
        name_normalized=norm_name,
        month=req.month,
        year=req.year,
        invoice_ids=invoice_ids,
        created_at=datetime.utcnow()
    )
    db.add(collection)

    # If clear_workspace is True, mark invoices as cleared from workspace
    if req.clear_workspace and invoice_ids:
        db.query(Invoice).filter(
            Invoice.id.in_(invoice_ids),
            Invoice.business_id == user.business_id
        ).update({Invoice.in_workspace: False}, synchronize_session=False)

    db.commit()
    db.refresh(collection)

    return {
        "id": collection.id,
        "name": collection.name,
        "month": collection.month,
        "year": collection.year,
        "invoice_count": len(collection.invoice_ids),
        "cleared_from_workspace": req.clear_workspace,
        "created_at": collection.created_at.isoformat()
    }


@router.post("/clear-workspace", status_code=status.HTTP_201_CREATED)
def clear_workspace(
    req: CreateCollectionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    req.clear_workspace = True
    return create_collection(req=req, user=user, db=db)


@router.get("")
def list_collections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cols = db.query(InvoiceCollection).filter(
        InvoiceCollection.business_id == user.business_id
    ).order_by(InvoiceCollection.created_at.desc()).all()

    results = []
    for c in cols:
        # Calculate total value of invoices in this collection
        total_paise = 0
        if c.invoice_ids:
            invs = db.query(Invoice.total).filter(
                Invoice.id.in_(c.invoice_ids),
                Invoice.business_id == user.business_id,
                Invoice.deleted_at.is_(None)
            ).all()
            total_paise = sum(i[0] for i in invs)

        results.append({
            "id": c.id,
            "name": c.name,
            "month": c.month,
            "year": c.year,
            "invoice_count": len(c.invoice_ids),
            "total_paise": total_paise,
            "created_at": c.created_at.isoformat()
        })
    return results


@router.get("/{collection_id}")
def get_collection(
    collection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    col = db.query(InvoiceCollection).filter(
        InvoiceCollection.id == collection_id,
        InvoiceCollection.business_id == user.business_id
    ).first()

    if not col:
        raise HTTPException(status_code=404, detail="Collection not found.")

    invoices = []
    total_paise = 0
    if col.invoice_ids:
        db_invoices = db.query(Invoice).filter(
            Invoice.id.in_(col.invoice_ids),
            Invoice.business_id == user.business_id,
            Invoice.deleted_at.is_(None)
        ).all()
        for inv in db_invoices:
            total_paise += inv.total
            invoices.append({
                "id": inv.id,
                "invoice_no": inv.invoice_no,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "party_name": inv.party.name if inv.party else "Unknown",
                "direction": inv.direction,
                "total": inv.total,
                "payment_status": inv.payment_status,
                "review_status": inv.review_status,
                "validation_status": inv.validation_status
            })

    return {
        "id": col.id,
        "name": col.name,
        "month": col.month,
        "year": col.year,
        "invoice_count": len(col.invoice_ids),
        "total_paise": total_paise,
        "created_at": col.created_at.isoformat(),
        "invoices": invoices
    }
