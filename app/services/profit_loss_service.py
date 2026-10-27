from sqlalchemy.orm import Session
from app.models.invoice import Invoice
from app.models.business import Business
from app.services.fy_service import filter_query_by_period, get_current_fy


def compute_profit_and_loss(
    db: Session,
    business_id: int,
    fy: int | None = None,
    quarter: str | None = None,
    month: str | None = None
) -> dict:
    """
    Computes Accrual Basis Profit and Loss:
    - Income: Taxable value of approved sales invoices
    - Expenses: Taxable value of approved purchase invoices
    - GST shown separately
    All figures in integer paise.
    """
    biz = db.query(Business).filter(Business.id == business_id).first()
    fy_start = biz.fy_start_month if biz else 4

    base_query = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.review_status == "approved",
        Invoice.deleted_at.is_(None)
    )

    filtered_query = filter_query_by_period(
        base_query, fy=fy, quarter=quarter, month=month, fy_start_month=fy_start
    )
    invoices = filtered_query.all()

    sales = [i for i in invoices if i.direction == "sales"]
    purchases = [i for i in invoices if i.direction in ["purchase", "unknown"]]

    income_taxable = sum(i.taxable for i in sales)
    sales_cgst = sum(i.cgst for i in sales)
    sales_sgst = sum(i.sgst for i in sales)
    sales_igst = sum(i.igst for i in sales)
    output_gst = sales_cgst + sales_sgst + sales_igst

    expense_taxable = sum(i.taxable for i in purchases)
    purchase_cgst = sum(i.cgst for i in purchases)
    purchase_sgst = sum(i.sgst for i in purchases)
    purchase_igst = sum(i.igst for i in purchases)
    input_gst = purchase_cgst + purchase_sgst + purchase_igst

    net_profit = income_taxable - expense_taxable

    return {
        "period": {
            "fy": fy,
            "quarter": quarter,
            "month": month
        },
        "income": {
            "sales_count": len(sales),
            "taxable": income_taxable,
            "cgst": sales_cgst,
            "sgst": sales_sgst,
            "igst": sales_igst,
            "total_gst": output_gst,
            "gross_total": sum(i.total for i in sales)
        },
        "expenses": {
            "purchase_count": len(purchases),
            "taxable": expense_taxable,
            "cgst": purchase_cgst,
            "sgst": purchase_sgst,
            "igst": purchase_igst,
            "total_gst": input_gst,
            "gross_total": sum(i.total for i in purchases)
        },
        "net_profit": net_profit
    }
