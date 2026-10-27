from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.invoice import Invoice, InvoiceItem
from app.models.user import User
from app.models.business import Business
from app.schemas.invoices import InvoiceUpdate
from app.extraction.validate import validate_invoice_data


def list_invoices(
    db: Session,
    business_id: int,
    direction: str | None = None,
    review_status: str | None = None,
    payment_status: str | None = None,
    party_id: int | None = None,
    month: str | None = None,  # YYYY-MM
    in_workspace: bool | None = None,
    page: int = 1,
    page_size: int = 50
) -> tuple[list[Invoice], int]:
    """Returns (invoices_list, total_count) strictly filtered by tenant business_id."""
    query = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.deleted_at.is_(None)
    )

    if in_workspace is not None:
        query = query.filter(Invoice.in_workspace == in_workspace)
    if direction and direction != "all":
        query = query.filter(Invoice.direction == direction)
    if review_status and review_status != "all":
        query = query.filter(Invoice.review_status == review_status)
    if payment_status and payment_status != "all":
        query = query.filter(Invoice.payment_status == payment_status)
    if party_id:
        query = query.filter(Invoice.party_id == party_id)
    if month:
        query = query.filter(Invoice.invoice_date.isnot(None))
        # Match YYYY-MM prefix
        query = query.filter(Invoice.invoice_date.cast(db.bind.dialect.types.String).like(f"{month}%"))

    total = query.count()
    invoices = (
        query.order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return invoices, total


def get_invoice(db: Session, business_id: int, invoice_id: int) -> Invoice:
    inv = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.business_id == business_id,
        Invoice.deleted_at.is_(None)
    ).first()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found."
        )
    return inv


def update_and_validate_invoice(
    db: Session,
    business_id: int,
    invoice_id: int,
    data: InvoiceUpdate
) -> Invoice:
    """Updates invoice fields and instantly re-runs validation."""
    inv = get_invoice(db, business_id, invoice_id)
    biz = db.query(Business).filter(Business.id == business_id).first()
    business_state = biz.state_code if biz else None

    update_dict = data.model_dump(exclude_unset=True)
    items_data = update_dict.pop("items", None)

    for k, v in update_dict.items():
        setattr(inv, k, v)

    # If items are updated, recreate items
    if items_data is not None:
        db.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv.id).delete()
        for it in items_data:
            item = InvoiceItem(
                invoice_id=inv.id,
                description=it["description"],
                hsn_sac=it.get("hsn_sac"),
                quantity=it.get("quantity", 1.0),
                unit=it.get("unit", "NOS"),
                rate=it.get("rate", 0),
                taxable=it.get("taxable", 0),
                gst_rate=it.get("gst_rate", 18.0),
                cgst=it.get("cgst", 0),
                sgst=it.get("sgst", 0),
                igst=it.get("igst", 0),
                amount=it.get("amount", 0)
            )
            db.add(item)

    # Re-run statutory validation
    val_payload = {
        "vendor": inv.party.name if inv.party else None,
        "invoice_no": inv.invoice_no,
        "date": inv.invoice_date,
        "supplier_gstin": inv.supplier_gstin,
        "subtotal": inv.taxable,
        "cgst": inv.cgst,
        "sgst": inv.sgst,
        "igst": inv.igst,
        "cess": inv.cess,
        "total": inv.total,
        "place_of_supply": inv.place_of_supply_state
    }
    val_status, issues = validate_invoice_data(val_payload, business_state_code=business_state)
    inv.validation_status = val_status
    inv.validation_issues = issues

    db.commit()
    db.refresh(inv)
    return inv


def approve_invoice(
    db: Session,
    business_id: int,
    invoice_id: int,
    current_user: User,
    direction: str | None = None
) -> Invoice:
    if current_user.role not in ["owner", "accountant"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff cannot approve invoices."
        )

    inv = get_invoice(db, business_id, invoice_id)

    # 1. Resolve transaction direction
    if direction in ["purchase", "sales"]:
        inv.direction = direction
    elif inv.direction == "unknown":
        # Check if supplier GSTIN matches business GSTIN (sales), otherwise default to purchase (inward)
        biz = db.query(Business).filter(Business.id == business_id).first()
        if biz and biz.gstin and inv.supplier_gstin and inv.supplier_gstin.upper() == biz.gstin.upper():
            inv.direction = "sales"
        else:
            inv.direction = "purchase"

    # 2. Update linked party type if party was set to customer but invoice is purchase
    if inv.party and inv.direction == "purchase" and inv.party.type == "customer":
        inv.party.type = "vendor"

    inv.review_status = "approved"
    inv.approved_by = current_user.id
    inv.approved_at = datetime.utcnow()

    db.commit()
    db.refresh(inv)
    return inv


def reject_invoice(
    db: Session,
    business_id: int,
    invoice_id: int,
    current_user: User
) -> Invoice:
    if current_user.role not in ["owner", "accountant"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff cannot reject invoices."
        )

    inv = get_invoice(db, business_id, invoice_id)
    inv.review_status = "rejected"
    db.commit()
    db.refresh(inv)
    return inv


def delete_invoice(
    db: Session,
    business_id: int,
    invoice_id: int
) -> None:
    inv = get_invoice(db, business_id, invoice_id)
    inv.deleted_at = datetime.utcnow()
    db.commit()
