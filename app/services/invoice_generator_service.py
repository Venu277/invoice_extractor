import io
from datetime import date, timedelta, datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.models.invoice import Invoice, InvoiceItem
from app.models.party import Party
from app.models.business import Business
from app.models.user import User
from app.schemas.generator import GenerateInvoiceRequest
from app.services.money import round_half_up, format_inr, paise_to_decimal
from app.services.fy_service import get_current_fy
from app.extraction.validate import validate_invoice_data


def generate_sales_invoice(
    db: Session,
    business_id: int,
    user_id: int,
    req: GenerateInvoiceRequest
) -> Invoice:
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found.")

    customer = db.query(Party).filter(
        Party.id == req.customer_id,
        Party.business_id == business_id
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    # Numbering sequence: prefix + FY + serial (e.g. INV-2526-0001)
    fy = get_current_fy(biz.fy_start_month, req.invoice_date)
    fy_short = f"{str(fy)[-2:]}{str(fy + 1)[-2:]}"
    prefix = biz.invoice_prefix or "INV-"

    # Count existing generated sales invoices in this FY
    count = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.direction == "sales",
        Invoice.source == "generated"
    ).count()
    invoice_no = f"{prefix}{fy_short}-{count + 1:04d}"

    # Due date from customer terms or business default
    terms_days = customer.payment_terms_days or biz.default_payment_terms_days or 30
    due_date = req.invoice_date + timedelta(days=terms_days)

    # Tax rules based on state
    # Same state = intra-state (CGST + SGST); Different state = inter-state (IGST)
    biz_state = biz.state_code or "29"
    cust_state = customer.state_code or biz_state
    is_intra_state = (biz_state == cust_state)

    total_taxable = 0
    total_cgst = 0
    total_sgst = 0
    total_igst = 0
    total_amount = 0

    item_records = []
    for it in req.items:
        qty_dec = Decimal(str(it.quantity))
        rate_paise = it.rate_paise
        taxable_paise = int(round_half_up(Decimal(rate_paise) * qty_dec, 0))

        rate_gst_dec = Decimal(str(it.gst_rate))
        tax_total_paise = int(round_half_up(Decimal(taxable_paise) * (rate_gst_dec / Decimal("100")), 0))

        if is_intra_state:
            half_tax = tax_total_paise // 2
            cgst_p = half_tax
            sgst_p = tax_total_paise - half_tax
            igst_p = 0
        else:
            cgst_p = 0
            sgst_p = 0
            igst_p = tax_total_paise

        line_total = taxable_paise + tax_total_paise

        total_taxable += taxable_paise
        total_cgst += cgst_p
        total_sgst += sgst_p
        total_igst += igst_p
        total_amount += line_total

        item_records.append({
            "description": it.description,
            "hsn_sac": it.hsn_sac,
            "quantity": it.quantity,
            "unit": it.unit,
            "rate": rate_paise,
            "taxable": taxable_paise,
            "gst_rate": it.gst_rate,
            "cgst": cgst_p,
            "sgst": sgst_p,
            "igst": igst_p,
            "amount": line_total
        })

    # Create Invoice record (saved as approved sales invoice)
    inv = Invoice(
        business_id=business_id,
        party_id=customer.id,
        direction="sales",
        source="generated",
        invoice_no=invoice_no,
        invoice_date=req.invoice_date,
        due_date=due_date,
        supplier_gstin=biz.gstin,
        buyer_gstin=customer.gstin,
        place_of_supply_state=cust_state,
        taxable=total_taxable,
        cgst=total_cgst,
        sgst=total_sgst,
        igst=total_igst,
        cess=0,
        total=total_amount,
        amount_paid=0,
        payment_status="unpaid",
        review_status="approved",
        approved_by=user_id,
        approved_at=datetime.utcnow(),
        created_by=user_id
    )
    db.add(inv)
    db.flush()

    for r in item_records:
        it_obj = InvoiceItem(invoice_id=inv.id, **r)
        db.add(it_obj)

    # Validate generated invoice through the statutory validation function
    val_data = {
        "vendor": biz.name,
        "invoice_no": inv.invoice_no,
        "date": inv.invoice_date,
        "supplier_gstin": inv.supplier_gstin,
        "subtotal": inv.taxable,
        "cgst": inv.cgst,
        "sgst": inv.sgst,
        "igst": inv.igst,
        "total": inv.total,
        "place_of_supply": inv.place_of_supply_state
    }
    st_val, issues = validate_invoice_data(val_data, business_state_code=biz_state)
    inv.validation_status = st_val
    inv.validation_issues = issues

    db.commit()
    db.refresh(inv)
    return inv


def generate_sales_invoice_pdf(db: Session, business_id: int, invoice_id: int) -> bytes:
    """Renders a professional sales invoice PDF using ReportLab with bank and logo details."""
    inv = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.business_id == business_id
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    biz = inv.business
    customer = inv.party

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm
    )
    styles = getSampleStyleSheet()
    full_w = A4[0] - 30 * mm
    story = []

    # Header Banner
    title_style = ParagraphStyle("InvTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=18, textColor=colors.HexColor("#1F3A5F"))
    norm_style = ParagraphStyle("InvNorm", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=13)
    bold_style = ParagraphStyle("InvBold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=13)

    header_table = Table([
        [Paragraph(f"<b>{biz.name}</b><br/>{biz.address or ''}<br/>GSTIN: {biz.gstin or 'URP'}", norm_style),
         Paragraph(f"<b>TAX INVOICE</b><br/><b>Invoice No:</b> {inv.invoice_no}<br/><b>Date:</b> {inv.invoice_date}<br/><b>Due Date:</b> {inv.due_date}", norm_style)]
    ], colWidths=[full_w * 0.55, full_w * 0.45])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#1F3A5F")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8)
    ]))
    story += [header_table, Spacer(1, 10)]

    # Bill To
    c_name = customer.name if customer else "Customer"
    c_addr = customer.address if customer and customer.address else ""
    c_gstin = customer.gstin if customer and customer.gstin else "Unregistered"
    bill_table = Table([
        [Paragraph(f"<b>Bill To:</b><br/><b>{c_name}</b><br/>{c_addr}<br/>GSTIN: {c_gstin}<br/>Place of Supply: {inv.place_of_supply_state or ''}", norm_style)]
    ], colWidths=[full_w])
    bill_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
        ("PADDING", (0, 0), (-1, -1), 8)
    ]))
    story += [bill_table, Spacer(1, 12)]

    # Items Table
    rows = [["#", "Item Description", "HSN/SAC", "Qty", "Rate", "Taxable", "GST", "Amount"]]
    for idx, item in enumerate(inv.items, 1):
        tax_item = item.cgst + item.sgst + item.igst
        rows.append([
            str(idx),
            item.description,
            item.hsn_sac or "-",
            f"{float(item.quantity):.1f} {item.unit or ''}",
            format_inr(item.rate),
            format_inr(item.taxable),
            f"{float(item.gst_rate):.0f}%",
            format_inr(item.amount)
        ])

    item_table = Table(rows, colWidths=[10 * mm, 50 * mm, 20 * mm, 20 * mm, 22 * mm, 24 * mm, 16 * mm, 26 * mm])
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C9CED6")),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT")
    ]))
    story += [item_table, Spacer(1, 10)]

    # Totals Table
    totals_data = [
        ["Subtotal (Taxable):", format_inr(inv.taxable)],
        ["CGST:", format_inr(inv.cgst)],
        ["SGST:", format_inr(inv.sgst)],
        ["IGST:", format_inr(inv.igst)],
        ["Grand Total:", format_inr(inv.total)]
    ]
    tot_table = Table(totals_data, colWidths=[full_w * 0.75, full_w * 0.25])
    tot_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#1F3A5F"))
    ]))
    story += [tot_table, Spacer(1, 14)]

    # Bank Details Footer
    bank_lines = []
    if biz.bank_name:
        bank_lines.append(f"Bank: {biz.bank_name}")
    if biz.account_no:
        bank_lines.append(f"A/C: {biz.account_no}")
    if biz.ifsc:
        bank_lines.append(f"IFSC: {biz.ifsc}")
    if biz.upi_id:
        bank_lines.append(f"UPI ID: {biz.upi_id}")

    if bank_lines:
        b_text = " &nbsp;|&nbsp; ".join(bank_lines)
        b_para = Paragraph(f"<b>Bank & Payment Details:</b> {b_text}", norm_style)
        b_box = Table([[b_para]], colWidths=[full_w])
        b_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
            ("PADDING", (0, 0), (-1, -1), 6)
        ]))
        story.append(b_box)

    doc.build(story)
    return buffer.getvalue()
