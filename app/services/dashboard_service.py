from datetime import date
from collections import defaultdict
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.business import Business
from app.models.alert import Alert
from app.services.fy_service import filter_query_by_period, get_current_fy
from app.services.insights_service import generate_insights
from app.services.alerts_service import check_and_create_due_alerts, check_gst_deadline_alerts


def get_dashboard_data(
    db: Session,
    business_id: int,
    fy: int | None = None,
    month: str | None = None
) -> dict:
    biz = db.query(Business).filter(Business.id == business_id).first()
    fy_start = biz.fy_start_month if biz else 4
    if not fy and not month:
        fy = get_current_fy(fy_start)

    # Trigger proactive check for due and GST alerts
    check_and_create_due_alerts(db, business_id)
    check_gst_deadline_alerts(db, business_id)

    # Base query for all non-deleted invoices in tenant
    all_invoices = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.deleted_at.is_(None)
    ).all()

    # Filtered invoices for chosen period
    filtered_query = filter_query_by_period(
        db.query(Invoice).filter(Invoice.business_id == business_id, Invoice.deleted_at.is_(None)),
        fy=fy, month=month, fy_start_month=fy_start
    )
    period_invoices = filtered_query.all()

    # Period aggregates (Approved only for revenue/expense)
    approved_period = [i for i in period_invoices if i.review_status == "approved"]
    sales_invoices = [i for i in approved_period if i.direction == "sales"]
    purchase_invoices = [i for i in approved_period if i.direction in ["purchase", "unknown"]]

    sales_total = sum(i.total for i in sales_invoices)
    purchase_total = sum(i.total for i in purchase_invoices)
    output_gst = sum(i.cgst + i.sgst + i.igst + i.cess for i in sales_invoices)
    input_gst = sum(i.cgst + i.sgst + i.igst + i.cess for i in purchase_invoices)

    # Outstanding amounts across all active approved invoices
    active_approved = [i for i in all_invoices if i.review_status == "approved"]
    receivables_outstanding = sum(
        i.total - i.amount_paid for i in active_approved
        if i.direction == "sales" and i.payment_status in ["unpaid", "partial"]
    )
    payables_outstanding = sum(
        i.total - i.amount_paid for i in active_approved
        if i.direction in ["purchase", "unknown"] and i.payment_status in ["unpaid", "partial"]
    )

    pending_review_count = sum(1 for i in all_invoices if i.review_status == "pending_review")

    # Month-on-month change calculation
    mom_change_pct = 0.0
    today = date.today()
    cur_month_str = f"{today.year}-{today.month:02d}"
    last_month_date = today.replace(day=1) - date.resolution
    prev_month_str = f"{last_month_date.year}-{last_month_date.month:02d}"

    cur_sales = sum(
        i.total for i in all_invoices
        if i.direction == "sales" and i.review_status == "approved"
        and i.invoice_date and f"{i.invoice_date.year}-{i.invoice_date.month:02d}" == cur_month_str
    )
    prev_sales = sum(
        i.total for i in all_invoices
        if i.direction == "sales" and i.review_status == "approved"
        and i.invoice_date and f"{i.invoice_date.year}-{i.invoice_date.month:02d}" == prev_month_str
    )
    if prev_sales > 0:
        mom_change_pct = round(((cur_sales - prev_sales) / prev_sales) * 100.0, 1)

    # Top 5 Parties
    top_vendors = defaultdict(int)
    top_customers = defaultdict(int)
    for i in approved_period:
        name = i.party.name if i.party else "Unknown"
        if i.direction == "purchase":
            top_vendors[name] += i.total
        elif i.direction == "sales":
            top_customers[name] += i.total

    sorted_vendors = sorted(
        [{"name": k, "amount": v} for k, v in top_vendors.items()],
        key=lambda x: x["amount"], reverse=True
    )[:5]
    sorted_customers = sorted(
        [{"name": k, "amount": v} for k, v in top_customers.items()],
        key=lambda x: x["amount"], reverse=True
    )[:5]

    # Generate insights
    insights = generate_insights(db, business_id, all_invoices)

    # Unread alerts
    alerts = (
        db.query(Alert)
        .filter(Alert.business_id == business_id, Alert.is_read.is_(False))
        .order_by(Alert.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "period": {"fy": fy, "month": month},
        "sales_total": sales_total,
        "purchase_total": purchase_total,
        "output_gst": output_gst,
        "input_gst": input_gst,
        "receivables_outstanding": receivables_outstanding,
        "payables_outstanding": payables_outstanding,
        "pending_review_count": pending_review_count,
        "mom_change_pct": mom_change_pct,
        "top_vendors": sorted_vendors,
        "top_customers": sorted_customers,
        "insights": insights,
        "alerts": [
            {
                "id": a.id,
                "type": a.type,
                "severity": a.severity,
                "message": a.message,
                "created_at": a.created_at.isoformat()
            }
            for a in alerts
        ]
    }
