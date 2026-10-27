import re
from datetime import date, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.party import Party
from app.models.business import Business
from app.schemas.payments import PaymentCreate, PartyLedgerResponse, PartyLedgerEntry


def parse_terms_days(terms: str | None) -> int | None:
    if not terms:
        return None
    # Matches: Net 30, Due in 15 days, 45 days credit
    m = re.search(r"(?:net\s*|due\s*(?:in\s*)?)(\d+)", terms, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m2 = re.search(r"(\d+)\s*days?", terms, re.IGNORECASE)
    if m2:
        return int(m2.group(1))
    return None


def resolve_invoice_due_date(
    invoice_date: date | None,
    extracted_due_date: date | None,
    extracted_terms: str | None,
    party_terms_days: int | None,
    business_default_terms_days: int = 30
) -> date | None:
    """
    Resolves due date strictly in priority order:
    1. Extracted due date
    2. Invoice date + extracted terms days
    3. Invoice date + party terms days
    4. Invoice date + business default terms days
    """
    if extracted_due_date:
        return extracted_due_date

    if not invoice_date:
        return None

    # 2. Extracted terms
    term_days = parse_terms_days(extracted_terms)
    if term_days is not None:
        return invoice_date + timedelta(days=term_days)

    # 3. Party default terms
    if party_terms_days is not None and party_terms_days > 0:
        return invoice_date + timedelta(days=party_terms_days)

    # 4. Business default terms
    return invoice_date + timedelta(days=business_default_terms_days or 30)


def record_payment(
    db: Session,
    business_id: int,
    user_id: int,
    data: PaymentCreate
) -> tuple[Payment, Invoice]:
    """Records a payment and re-computes invoice payment status."""
    inv = db.query(Invoice).filter(
        Invoice.id == data.invoice_id,
        Invoice.business_id == business_id,
        Invoice.deleted_at.is_(None)
    ).first()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found."
        )

    # Record payment
    payment = Payment(
        business_id=business_id,
        invoice_id=inv.id,
        amount=data.amount,
        paid_on=data.paid_on,
        method=data.method,
        reference=data.reference,
        note=data.note,
        created_by=user_id
    )
    db.add(payment)
    db.flush()

    # Recalculate invoice amount_paid
    total_paid = sum(p.amount for p in inv.payments)
    inv.amount_paid = total_paid

    if inv.amount_paid >= inv.total:
        inv.payment_status = "paid"
    elif inv.amount_paid > 0:
        inv.payment_status = "partial"
    else:
        inv.payment_status = "unpaid"

    db.commit()
    db.refresh(payment)
    db.refresh(inv)
    return payment, inv


def list_invoice_payments(
    db: Session, business_id: int, invoice_id: int
) -> list[Payment]:
    return (
        db.query(Payment)
        .filter(Payment.business_id == business_id, Payment.invoice_id == invoice_id)
        .order_by(Payment.paid_on.desc(), Payment.id.desc())
        .all()
    )


def get_party_ledger(
    db: Session, business_id: int, party_id: int
) -> PartyLedgerResponse:
    """
    Computes complete statement of account / ledger for a party:
    Lists invoices and payments, computing chronological running balance in paise.
    """
    party = db.query(Party).filter(
        Party.id == party_id,
        Party.business_id == business_id
    ).first()
    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Party not found."
        )

    # Get all active approved invoices for party
    invoices = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.party_id == party_id,
        Invoice.deleted_at.is_(None),
        Invoice.review_status == "approved"
    ).all()

    # Get all payments associated with these invoices
    inv_ids = [i.id for i in invoices]
    payments = db.query(Payment).filter(
        Payment.business_id == business_id,
        Payment.invoice_id.in_(inv_ids)
    ).all() if inv_ids else []

    # Combine events
    events = []
    for inv in invoices:
        is_sales = (inv.direction == "sales")
        events.append({
            "date": inv.invoice_date or date(2000, 1, 1),
            "created_at": inv.created_at,
            "type": "invoice",
            "ref_id": inv.id,
            "ref_no": inv.invoice_no,
            "desc": f"Invoice {inv.invoice_no} ({'Sales' if is_sales else 'Purchase'})",
            # For sales: debit customer; for purchase: credit vendor
            "debit": inv.total if is_sales else 0,
            "credit": inv.total if not is_sales else 0
        })

    for p in payments:
        # Payment received (from customer): credit customer
        # Payment made (to vendor): debit vendor
        inv = next((i for i in invoices if i.id == p.invoice_id), None)
        is_sales = inv and (inv.direction == "sales")
        events.append({
            "date": p.paid_on,
            "created_at": p.created_at,
            "type": "payment",
            "ref_id": p.id,
            "ref_no": p.reference or f"PAY-{p.id}",
            "desc": f"Payment via {p.method.upper()}",
            "debit": p.amount if not is_sales else 0,
            "credit": p.amount if is_sales else 0
        })

    # Sort chronological
    events.sort(key=lambda x: (x["date"], x["created_at"]))

    running_balance = 0
    total_debit = 0
    total_credit = 0
    entries = []

    for ev in events:
        debit = ev["debit"]
        credit = ev["credit"]
        total_debit += debit
        total_credit += credit
        # Balance = debit - credit
        running_balance += (debit - credit)
        entries.append(PartyLedgerEntry(
            date=ev["date"],
            type=ev["type"],
            reference_id=ev["ref_id"],
            reference_no=ev["ref_no"],
            description=ev["desc"],
            debit=debit,
            credit=credit,
            balance=running_balance
        ))

    return PartyLedgerResponse(
        party_id=party.id,
        party_name=party.name,
        party_type=party.type,
        total_debit=total_debit,
        total_credit=total_credit,
        current_balance=running_balance,
        entries=entries
    )
