from collections import defaultdict
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceItem
from app.models.business import Business
from app.services.fy_service import filter_query_by_period, get_current_fy
from app.gst.rules import is_valid_gstin_format


DISCLAIMER_NOTE = (
    "NOTE: These are working calculations derived from approved invoices for accounting review. "
    "This is not an official statutory tax return filing."
)


def compute_tax_set_off(
    output_igst: int,
    output_cgst: int,
    output_sgst: int,
    itc_igst: int,
    itc_cgst: int,
    itc_sgst: int
) -> dict[str, int]:
    """
    Statutory Indian GST tax set-off rules (Section 49 / 49A / 49B):
    1. IGST credit against IGST, then CGST, then SGST.
    2. CGST credit against CGST, then IGST (never SGST).
    3. SGST credit against SGST, then IGST.
    All figures in integer paise.
    """
    rem_igst_liab = output_igst
    rem_cgst_liab = output_cgst
    rem_sgst_liab = output_sgst

    rem_igst_credit = itc_igst
    rem_cgst_credit = itc_cgst
    rem_sgst_credit = itc_sgst

    # 1. IGST Credit set-off
    used_igst_igst = min(rem_igst_credit, rem_igst_liab)
    rem_igst_liab -= used_igst_igst
    rem_igst_credit -= used_igst_igst

    used_igst_cgst = min(rem_igst_credit, rem_cgst_liab)
    rem_cgst_liab -= used_igst_cgst
    rem_igst_credit -= used_igst_cgst

    used_igst_sgst = min(rem_igst_credit, rem_sgst_liab)
    rem_sgst_liab -= used_igst_sgst
    rem_igst_credit -= used_igst_sgst

    # 2. CGST Credit set-off
    used_cgst_cgst = min(rem_cgst_credit, rem_cgst_liab)
    rem_cgst_liab -= used_cgst_cgst
    rem_cgst_credit -= used_cgst_cgst

    used_cgst_igst = min(rem_cgst_credit, rem_igst_liab)
    rem_igst_liab -= used_cgst_igst
    rem_cgst_credit -= used_cgst_igst

    # 3. SGST Credit set-off
    used_sgst_sgst = min(rem_sgst_credit, rem_sgst_liab)
    rem_sgst_liab -= used_sgst_sgst
    rem_sgst_credit -= used_sgst_sgst

    used_sgst_igst = min(rem_sgst_credit, rem_igst_liab)
    rem_igst_liab -= used_sgst_igst
    rem_sgst_credit -= used_sgst_igst

    return {
        "cash_payable_igst": rem_igst_liab,
        "cash_payable_cgst": rem_cgst_liab,
        "cash_payable_sgst": rem_sgst_liab,
        "total_cash_payable": rem_igst_liab + rem_cgst_liab + rem_sgst_liab,
        "carried_forward_igst": rem_igst_credit,
        "carried_forward_cgst": rem_cgst_credit,
        "carried_forward_sgst": rem_sgst_credit
    }


def compute_gstr1_summary(
    db: Session,
    business_id: int,
    fy: int | None = None,
    month: str | None = None
) -> dict:
    """
    GSTR-1 style summary:
    - B2B sales: Customer has valid GSTIN
    - B2C sales: Customer has no valid GSTIN
    Grouped by tax rate. All values in integer paise.
    """
    biz = db.query(Business).filter(Business.id == business_id).first()
    fy_start = biz.fy_start_month if biz else 4

    query = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.direction == "sales",
        Invoice.review_status == "approved",
        Invoice.deleted_at.is_(None)
    )
    query = filter_query_by_period(query, fy=fy, month=month, fy_start_month=fy_start)
    sales_invoices = query.all()

    b2b_groups = defaultdict(lambda: {"taxable": 0, "cgst": 0, "sgst": 0, "igst": 0, "total": 0})
    b2c_groups = defaultdict(lambda: {"taxable": 0, "cgst": 0, "sgst": 0, "igst": 0, "total": 0})

    for inv in sales_invoices:
        # Determine B2B vs B2C
        is_b2b = bool(inv.buyer_gstin and is_valid_gstin_format(inv.buyer_gstin))
        target_group = b2b_groups if is_b2b else b2c_groups

        if inv.items:
            for item in inv.items:
                rate_key = float(item.gst_rate)
                target_group[rate_key]["taxable"] += item.taxable
                target_group[rate_key]["cgst"] += item.cgst
                target_group[rate_key]["sgst"] += item.sgst
                target_group[rate_key]["igst"] += item.igst
                target_group[rate_key]["total"] += item.amount
        else:
            # Header fallback rate
            tax_total = inv.cgst + inv.sgst + inv.igst
            rate_key = round((tax_total / inv.taxable * 100.0), 1) if inv.taxable > 0 else 0.0
            target_group[rate_key]["taxable"] += inv.taxable
            target_group[rate_key]["cgst"] += inv.cgst
            target_group[rate_key]["sgst"] += inv.sgst
            target_group[rate_key]["igst"] += inv.igst
            target_group[rate_key]["total"] += inv.total

    return {
        "disclaimer": DISCLAIMER_NOTE,
        "b2b": [{"rate": k, **v} for k, v in sorted(b2b_groups.items())],
        "b2c": [{"rate": k, **v} for k, v in sorted(b2c_groups.items())],
        "total_sales_taxable": sum(i.taxable for i in sales_invoices),
        "total_output_gst": sum(i.cgst + i.sgst + i.igst for i in sales_invoices)
    }


def compute_gstr3b_summary(
    db: Session,
    business_id: int,
    fy: int | None = None,
    month: str | None = None
) -> dict:
    """
    GSTR-3B style summary:
    - Outward taxable supplies
    - Eligible ITC & Ineligible ITC (invalid GSTINs)
    - Net liability after statutory tax set-off
    All values in integer paise.
    """
    biz = db.query(Business).filter(Business.id == business_id).first()
    fy_start = biz.fy_start_month if biz else 4

    query = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.review_status == "approved",
        Invoice.deleted_at.is_(None)
    )
    query = filter_query_by_period(query, fy=fy, month=month, fy_start_month=fy_start)
    invoices = query.all()

    sales = [i for i in invoices if i.direction == "sales"]
    purchases = [i for i in invoices if i.direction in ["purchase", "unknown"]]

    # Outward Taxable Supplies
    outward_taxable = sum(i.taxable for i in sales)
    outward_cgst = sum(i.cgst for i in sales)
    outward_sgst = sum(i.sgst for i in sales)
    outward_igst = sum(i.igst for i in sales)

    # Input Tax Credit
    eligible_purchases = [i for i in purchases if i.supplier_gstin and is_valid_gstin_format(i.supplier_gstin)]
    ineligible_purchases = [i for i in purchases if not i.supplier_gstin or not is_valid_gstin_format(i.supplier_gstin)]

    itc_cgst = sum(i.cgst for i in eligible_purchases)
    itc_sgst = sum(i.sgst for i in eligible_purchases)
    itc_igst = sum(i.igst for i in eligible_purchases)

    ineligible_tax = sum(i.cgst + i.sgst + i.igst for i in ineligible_purchases)

    # Statutory Set-off
    set_off = compute_tax_set_off(
        output_igst=outward_igst,
        output_cgst=outward_cgst,
        output_sgst=outward_sgst,
        itc_igst=itc_igst,
        itc_cgst=itc_cgst,
        itc_sgst=itc_sgst
    )

    return {
        "disclaimer": DISCLAIMER_NOTE,
        "outward_supplies": {
            "taxable": outward_taxable,
            "cgst": outward_cgst,
            "sgst": outward_sgst,
            "igst": outward_igst,
            "total_tax": outward_cgst + outward_sgst + outward_igst
        },
        "itc_eligible": {
            "cgst": itc_cgst,
            "sgst": itc_sgst,
            "igst": itc_igst,
            "total_itc": itc_cgst + itc_sgst + itc_igst
        },
        "itc_ineligible": {
            "ineligible_count": len(ineligible_purchases),
            "ineligible_tax": ineligible_tax
        },
        "set_off_summary": set_off
    }


def compute_hsn_summary(
    db: Session,
    business_id: int,
    fy: int | None = None,
    month: str | None = None
) -> dict:
    """
    HSN/SAC summary:
    Grouped by HSN or SAC and GST rate, with total quantity, taxable value, and tax.
    """
    biz = db.query(Business).filter(Business.id == business_id).first()
    fy_start = biz.fy_start_month if biz else 4

    query = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.review_status == "approved",
        Invoice.deleted_at.is_(None)
    )
    query = filter_query_by_period(query, fy=fy, month=month, fy_start_month=fy_start)
    invoices = query.all()

    hsn_groups = defaultdict(lambda: {"quantity": 0.0, "taxable": 0, "cgst": 0, "sgst": 0, "igst": 0, "total_tax": 0})

    for inv in invoices:
        if inv.items:
            for item in inv.items:
                hsn = item.hsn_sac or "OTHER"
                rate = float(item.gst_rate)
                key = (hsn, rate)
                hsn_groups[key]["quantity"] += float(item.quantity)
                hsn_groups[key]["taxable"] += item.taxable
                hsn_groups[key]["cgst"] += item.cgst
                hsn_groups[key]["sgst"] += item.sgst
                hsn_groups[key]["igst"] += item.igst
                hsn_groups[key]["total_tax"] += (item.cgst + item.sgst + item.igst)
        else:
            # Fallback to invoice header tax values
            tax_total = inv.cgst + inv.sgst + inv.igst
            rate = round((tax_total / inv.taxable * 100.0), 1) if inv.taxable > 0 else 0.0
            key = ("GENERAL / SERVICES", rate)
            hsn_groups[key]["quantity"] += 1.0
            hsn_groups[key]["taxable"] += inv.taxable
            hsn_groups[key]["cgst"] += inv.cgst
            hsn_groups[key]["sgst"] += inv.sgst
            hsn_groups[key]["igst"] += inv.igst
            hsn_groups[key]["total_tax"] += tax_total

    rows = []
    for (hsn, rate), data in sorted(hsn_groups.items()):
        rows.append({
            "hsn_sac": hsn,
            "gst_rate": rate,
            "quantity": data["quantity"],
            "taxable": data["taxable"],
            "cgst": data["cgst"],
            "sgst": data["sgst"],
            "igst": data["igst"],
            "total_tax": data["total_tax"]
        })

    return {
        "disclaimer": DISCLAIMER_NOTE,
        "rows": rows
    }
