from datetime import date
from collections import defaultdict
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.party import Party
from app.schemas.payments import AgeingReportResponse, AgeingBucket, PartyAgeingRow


def compute_ageing_report(
    db: Session,
    business_id: int,
    direction: str = "sales",  # sales = receivables, purchase = payables
    as_of: date | None = None
) -> AgeingReportResponse:
    as_of_date = as_of or date.today()

    # Query approved, unpaid or partial invoices
    invoices = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.direction == direction,
        Invoice.review_status == "approved",
        Invoice.payment_status.in_(["unpaid", "partial"]),
        Invoice.deleted_at.is_(None)
    ).all()

    # Buckets by party
    party_buckets: dict[int, dict[str, int]] = defaultdict(lambda: {
        "not_due": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0, "total": 0
    })
    party_names: dict[int, str] = {}

    summary = {
        "not_due": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0, "total": 0
    }

    for inv in invoices:
        outstanding_paise = inv.total - inv.amount_paid
        if outstanding_paise <= 0:
            continue

        p_id = inv.party_id or 0
        if p_id not in party_names:
            party_names[p_id] = inv.party.name if inv.party else "Unknown Party"

        due_date = inv.due_date or inv.invoice_date or as_of_date
        overdue_days = (as_of_date - due_date).days

        bucket_key = "not_due"
        if overdue_days <= 0:
            bucket_key = "not_due"
        elif 1 <= overdue_days <= 30:
            bucket_key = "1_30"
        elif 31 <= overdue_days <= 60:
            bucket_key = "31_60"
        elif 61 <= overdue_days <= 90:
            bucket_key = "61_90"
        else:
            bucket_key = "90_plus"

        party_buckets[p_id][bucket_key] += outstanding_paise
        party_buckets[p_id]["total"] += outstanding_paise

        summary[bucket_key] += outstanding_paise
        summary["total"] += outstanding_paise

    breakdown_rows: list[PartyAgeingRow] = []
    for p_id, b in party_buckets.items():
        breakdown_rows.append(PartyAgeingRow(
            party_id=p_id,
            party_name=party_names[p_id],
            buckets=AgeingBucket(
                not_due=b["not_due"],
                days_1_30=b["1_30"],
                days_31_60=b["31_60"],
                days_61_90=b["61_90"],
                days_90_plus=b["90_plus"],
                total_outstanding=b["total"]
            )
        ))

    # Sort by total outstanding descending
    breakdown_rows.sort(key=lambda r: r.buckets.total_outstanding, reverse=True)

    return AgeingReportResponse(
        direction=direction,
        as_of_date=as_of_date,
        summary=AgeingBucket(
            not_due=summary["not_due"],
            days_1_30=summary["1_30"],
            days_31_60=summary["31_60"],
            days_61_90=summary["61_90"],
            days_90_plus=summary["90_plus"],
            total_outstanding=summary["total"]
        ),
        party_breakdown=breakdown_rows
    )
