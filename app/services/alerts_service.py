from datetime import date, timedelta
from statistics import median
from sqlalchemy.orm import Session

from app.config import settings
from app.models.alert import Alert
from app.models.invoice import Invoice
from app.models.party import Party
from app.services.money import format_inr


def create_alert_if_not_exists(
    db: Session,
    business_id: int,
    alert_type: str,
    severity: str,
    message: str,
    dedupe_key: str,
    ref_type: str | None = None,
    ref_id: int | None = None
) -> Alert | None:
    """Creates alert with deduplication key; does nothing if key already exists for tenant."""
    existing = db.query(Alert).filter(
        Alert.business_id == business_id,
        Alert.dedupe_key == dedupe_key
    ).first()
    if existing:
        return existing

    alert = Alert(
        business_id=business_id,
        type=alert_type,
        severity=severity,
        message=message,
        dedupe_key=dedupe_key,
        ref_type=ref_type,
        ref_id=ref_id,
        is_read=False
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def check_and_create_due_alerts(db: Session, business_id: int, as_of: date | None = None):
    """Checks for invoices due within 3 days or already overdue."""
    today = as_of or date.today()
    three_days_later = today + timedelta(days=3)

    invoices = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.review_status == "approved",
        Invoice.payment_status.in_(["unpaid", "partial"]),
        Invoice.due_date.isnot(None),
        Invoice.deleted_at.is_(None)
    ).all()

    for inv in invoices:
        due = inv.due_date
        outstanding = inv.total - inv.amount_paid
        if outstanding <= 0:
            continue

        party_name = inv.party.name if inv.party else "Unknown"

        # Overdue alert
        if due < today:
            days_overdue = (today - due).days
            dedupe_key = f"overdue_{inv.id}_{today.strftime('%Y-%m-%d')}"
            msg = f"Invoice {inv.invoice_no} ({party_name}) is overdue by {days_overdue} day(s). Outstanding: {format_inr(outstanding)}."
            create_alert_if_not_exists(
                db, business_id, "overdue", "danger", msg, dedupe_key, "invoice", inv.id
            )

        # Due soon alert (within 3 days)
        elif today <= due <= three_days_later:
            days_left = (due - today).days
            dedupe_key = f"due_soon_{inv.id}_{due.strftime('%Y-%m-%d')}"
            msg = f"Invoice {inv.invoice_no} ({party_name}) is due in {days_left} day(s) on {due}. Amount: {format_inr(outstanding)}."
            create_alert_if_not_exists(
                db, business_id, "due_soon", "warning", msg, dedupe_key, "invoice", inv.id
            )


def check_party_spike(db: Session, business_id: int, invoice: Invoice):
    """Alerts if invoice total exceeds 3x party median invoice amount."""
    if not invoice.party_id or invoice.total <= 0:
        return

    past_invoices = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.party_id == invoice.party_id,
        Invoice.id != invoice.id,
        Invoice.deleted_at.is_(None)
    ).all()

    if len(past_invoices) >= 3:
        amounts = [inv.total for inv in past_invoices if inv.total > 0]
        med = median(amounts)
        if med > 0 and invoice.total >= (med * 3):
            dedupe = f"spike_{invoice.id}"
            party_name = invoice.party.name if invoice.party else "Party"
            msg = f"Unusual amount: Invoice {invoice.invoice_no} ({format_inr(invoice.total)}) is more than 3x the median ({format_inr(int(med))}) for {party_name}."
            create_alert_if_not_exists(
                db, business_id, "spike", "warning", msg, dedupe, "invoice", invoice.id
            )


def check_gst_deadline_alerts(db: Session, business_id: int, as_of: date | None = None):
    """Alerts for upcoming GSTR-1 and GSTR-3B statutory filing deadlines."""
    today = as_of or date.today()
    y, m = today.year, today.month

    # GSTR-1 alert (due on settings.GST_GSTR1_DUE_DAY, e.g. 11th)
    gstr1_due = date(y, m, settings.GST_GSTR1_DUE_DAY)
    if today <= gstr1_due <= (today + timedelta(days=3)):
        dedupe = f"gstr1_{y}_{m}"
        msg = f"GST Reminder: GSTR-1 return for current period is due on {gstr1_due} (in {(gstr1_due - today).days} days)."
        create_alert_if_not_exists(
            db, business_id, "gst_reminder", "info", msg, dedupe
        )

    # GSTR-3B alert (due on settings.GST_GSTR3B_DUE_DAY, e.g. 20th)
    gstr3b_due = date(y, m, settings.GST_GSTR3B_DUE_DAY)
    if today <= gstr3b_due <= (today + timedelta(days=3)):
        dedupe = f"gstr3b_{y}_{m}"
        msg = f"GST Reminder: GSTR-3B monthly return and tax payment are due on {gstr3b_due} (in {(gstr3b_due - today).days} days)."
        create_alert_if_not_exists(
            db, business_id, "gst_reminder", "warning", msg, dedupe
        )
