from datetime import date
from collections import defaultdict
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.services.money import format_inr
from app.gst.rules import is_valid_gstin_format


def generate_insights(
    db: Session,
    business_id: int,
    invoices: list[Invoice],
    as_of: date | None = None
) -> list[str]:
    """Generates plain-language business insights using deterministic rules."""
    insights: list[str] = []
    as_of_date = as_of or date.today()

    # 1. Overdue Receivables Rule
    overdue_rec = [
        inv for inv in invoices
        if inv.direction == "sales"
        and inv.review_status == "approved"
        and inv.payment_status in ["unpaid", "partial"]
        and inv.due_date and inv.due_date < as_of_date
    ]
    if overdue_rec:
        total_overdue = sum(inv.total - inv.amount_paid for inv in overdue_rec)
        insights.append(
            f"You have {len(overdue_rec)} overdue customer invoice(s) totaling {format_inr(total_overdue)}."
        )

    # 2. Input Tax Credit at Risk Rule
    itc_at_risk = [
        inv for inv in invoices
        if inv.direction == "purchase"
        and inv.review_status == "approved"
        and (not inv.supplier_gstin or not is_valid_gstin_format(inv.supplier_gstin))
    ]
    if itc_at_risk:
        total_risk_tax = sum(inv.cgst + inv.sgst + inv.igst for inv in itc_at_risk)
        if total_risk_tax > 0:
            insights.append(
                f"{format_inr(total_risk_tax)} in Input Tax Credit (ITC) is at risk across {len(itc_at_risk)} purchase invoice(s) due to missing or invalid supplier GSTIN."
            )

    # 3. Supplier Spend Concentration Rule
    purchases = [inv for inv in invoices if inv.direction == "purchase" and inv.review_status == "approved"]
    total_spend = sum(inv.total for inv in purchases)
    if total_spend > 0:
        vendor_spend = defaultdict(int)
        for inv in purchases:
            name = inv.party.name if inv.party else "Unknown"
            vendor_spend[name] += inv.total

        top_vendor, top_amount = max(vendor_spend.items(), key=lambda x: x[1])
        share_pct = (top_amount / total_spend) * 100
        if share_pct >= 30.0:
            insights.append(
                f"{top_vendor} accounts for {share_pct:.1f}% of your total purchase spend ({format_inr(top_amount)})."
            )

    # 4. Pending Review Invoices
    pending = [inv for inv in invoices if inv.review_status == "pending_review"]
    if pending:
        insights.append(
            f"{len(pending)} newly extracted invoice(s) are awaiting review and approval."
        )

    return insights
