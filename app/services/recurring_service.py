from datetime import date, timedelta
from sqlalchemy.orm import Session
from dateutil.relativedelta import relativedelta

from app.models.recurring import RecurringTemplate
from app.models.invoice import Invoice
from app.schemas.generator import RecurringTemplateCreate, GenerateInvoiceRequest, GeneratorItem
from app.services.invoice_generator_service import generate_sales_invoice
from app.services.alerts_service import create_alert_if_not_exists
from app.services.money import format_inr


def create_recurring_template(
    db: Session,
    business_id: int,
    data: RecurringTemplateCreate
) -> RecurringTemplate:
    tmpl = RecurringTemplate(
        business_id=business_id,
        party_id=data.party_id,
        items=[it.model_dump() for it in data.items],
        frequency=data.frequency,
        next_run=data.start_date,
        end_date=data.end_date,
        active=True
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


def process_due_recurring_invoices(
    db: Session,
    as_of: date | None = None
) -> list[Invoice]:
    """
    Finds all active recurring templates due on or before as_of date.
    Generates invoice, advances next_run, and raises an alert.
    Idempotent.
    """
    today = as_of or date.today()
    due_templates = db.query(RecurringTemplate).filter(
        RecurringTemplate.active.is_(True),
        RecurringTemplate.next_run <= today
    ).all()

    created_invoices = []
    for tmpl in due_templates:
        # Check if past end date
        if tmpl.end_date and tmpl.next_run > tmpl.end_date:
            tmpl.active = False
            db.commit()
            continue

        # Prepare items
        items = [
            GeneratorItem(
                description=it["description"],
                hsn_sac=it.get("hsn_sac"),
                quantity=it["quantity"],
                unit=it.get("unit", "NOS"),
                rate_paise=it["rate_paise"],
                gst_rate=it.get("gst_rate", 18.0)
            )
            for it in tmpl.items
        ]

        req = GenerateInvoiceRequest(
            customer_id=tmpl.party_id,
            invoice_date=tmpl.next_run,
            items=items,
            notes=f"Auto-generated recurring invoice ({tmpl.frequency})"
        )

        # Generate invoice
        inv = generate_sales_invoice(
            db=db,
            business_id=tmpl.business_id,
            user_id=1,  # System generated
            req=req
        )
        tmpl.last_invoice_id = inv.id

        # Advance next_run based on frequency
        if tmpl.frequency == "weekly":
            tmpl.next_run += timedelta(days=7)
        elif tmpl.frequency == "monthly":
            tmpl.next_run += relativedelta(months=1)
        elif tmpl.frequency == "quarterly":
            tmpl.next_run += relativedelta(months=3)
        elif tmpl.frequency == "yearly":
            tmpl.next_run += relativedelta(years=1)

        # Check if new next_run is beyond end_date
        if tmpl.end_date and tmpl.next_run > tmpl.end_date:
            tmpl.active = False

        db.commit()

        # Create alert
        dedupe = f"recurring_inv_{inv.id}"
        msg = f"Recurring invoice {inv.invoice_no} ({format_inr(inv.total)}) generated for {inv.party.name if inv.party else 'Customer'}."
        create_alert_if_not_exists(
            db, tmpl.business_id, "recurring", "info", msg, dedupe, "invoice", inv.id
        )

        created_invoices.append(inv)

    return created_invoices
