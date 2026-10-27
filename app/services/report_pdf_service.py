import io
from datetime import datetime, date
from xml.sax.saxutils import escape
from sqlalchemy.orm import Session

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

from app.models.invoice import Invoice
from app.models.business import Business
from app.services.money import format_inr, paise_to_decimal

NAVY = colors.HexColor("#1f3a5f")
LIGHT = colors.HexColor("#f3f4f6")
LINE = colors.HexColor("#c9ced6")
RED_BG = colors.HexColor("#fdecea")

_base = getSampleStyleSheet()["Normal"]
S_TEXT = ParagraphStyle("t", parent=_base, fontName="Helvetica", fontSize=9.5, leading=13)
S_H = ParagraphStyle("h", parent=_base, fontName="Helvetica-Bold", fontSize=12.5, textColor=NAVY, spaceBefore=14, spaceAfter=6)
S_CELL = ParagraphStyle("c", parent=_base, fontName="Helvetica", fontSize=8.3, leading=10.5)
S_CELL_R = ParagraphStyle("cr", parent=S_CELL, alignment=2)
S_HEAD = ParagraphStyle("hd", parent=S_CELL, fontName="Helvetica-Bold", textColor=colors.white)
S_HEAD_R = ParagraphStyle("hdr", parent=S_HEAD, alignment=2)
S_BANNER1 = ParagraphStyle("b1", parent=_base, fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=colors.white)
S_BANNER2 = ParagraphStyle("b2", parent=_base, fontName="Helvetica", fontSize=11, leading=15, textColor=colors.white)
S_KPI = ParagraphStyle("k", parent=_base, fontName="Helvetica", fontSize=8, leading=14, textColor=colors.HexColor("#555555"))


def _grid(rows, widths, right_cols=(), header_bg=NAVY, extra=None):
    data = []
    for r, row in enumerate(rows):
        line = []
        for c, value in enumerate(row):
            if r == 0:
                style = S_HEAD_R if c in right_cols else S_HEAD
            else:
                style = S_CELL_R if c in right_cols else S_CELL
            line.append(Paragraph(escape(str(value if value is not None else "-")), style))
        data.append(line)
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5)
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    if extra:
        style += extra
    t.setStyle(TableStyle(style))
    return t


def _vendor_chart(vendors, width):
    row_h = 20
    d = Drawing(width, max(24, row_h * len(vendors) + 4))
    if not vendors:
        return d
    biggest = max(v["value"] for v in vendors) or 1
    label_w, bar_max = 150, width - 150 - 90
    for i, v in enumerate(vendors):
        y = (len(vendors) - 1 - i) * row_h + 4
        name = v["vendor"] if len(v["vendor"]) <= 28 else v["vendor"][:26] + ".."
        d.add(String(0, y + 4, name, fontName="Helvetica", fontSize=8.5, fillColor=colors.HexColor("#333333")))
        bar = max(2, bar_max * v["value"] / biggest)
        d.add(Rect(label_w, y, bar, 12, fillColor=NAVY, strokeColor=None))
        d.add(String(label_w + bar + 6, y + 3, format_inr(v["value"]), fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#333333")))
    return d


def generate_monthly_report_pdf(
    db: Session,
    business_id: int,
    month_key: str  # YYYY-MM
) -> bytes:
    biz = db.query(Business).filter(Business.id == business_id).first()
    business_name = biz.name if biz else "Business"

    # Look for a saved collection matching this month and year
    invoices = []
    try:
        from app.models.collection import InvoiceCollection
        m_parts = month_key.split("-")
        y_int, m_int = int(m_parts[0]), int(m_parts[1])
        col = db.query(InvoiceCollection).filter(
            InvoiceCollection.business_id == business_id,
            InvoiceCollection.year == y_int,
            InvoiceCollection.month == m_int
        ).first()
        if col and col.invoice_ids:
            col_invoices = db.query(Invoice).filter(
                Invoice.id.in_(col.invoice_ids),
                Invoice.business_id == business_id,
                Invoice.deleted_at.is_(None)
            ).all()
            if col_invoices:
                invoices = col_invoices
    except Exception:
        pass

    # Fallback to all approved invoices for this month
    if not invoices:
        all_invoices = db.query(Invoice).filter(
            Invoice.business_id == business_id,
            Invoice.review_status == "approved",
            Invoice.deleted_at.is_(None)
        ).all()
        invoices = [
            inv for inv in all_invoices
            if inv.invoice_date and inv.invoice_date.strftime("%Y-%m") == month_key
        ]

    total_value = sum(i.total for i in invoices)
    taxable_val = sum(i.taxable for i in invoices)
    cgst_val = sum(i.cgst for i in invoices)
    sgst_val = sum(i.sgst for i in invoices)
    igst_val = sum(i.igst for i in invoices)
    total_gst = cgst_val + sgst_val + igst_val
    ok_count = sum(1 for i in invoices if i.validation_status == "ok")
    issue_count = len(invoices) - ok_count

    # Month label
    dt_month = datetime.strptime(f"{month_key}-01", "%Y-%m-%d")
    period_str = dt_month.strftime("%B %Y")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=18 * mm,
        title=f"Monthly Summary - {period_str}", author=business_name
    )
    full_w = A4[0] - 30 * mm
    story = []

    # Banner
    banner = Table([[Paragraph(escape(business_name), S_BANNER1)],
                    [Paragraph(f"Monthly Invoice Summary Report &nbsp;|&nbsp; {period_str}", S_BANNER2)]],
                   colWidths=[full_w])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (0, 0), 14),
        ("BOTTOMPADDING", (0, 1), (0, 1), 14)
    ]))
    story += [banner, Spacer(1, 12)]

    # Executive Summary
    story.append(Paragraph("1. Executive Summary", S_H))
    n = len(invoices)
    avg_val = total_value // n if n > 0 else 0
    story.append(Paragraph(
        f"During {period_str}, <b>{n}</b> invoice(s) were processed with a combined value of "
        f"<b>{format_inr(total_value)}</b>, of which <b>{format_inr(total_gst)}</b> is GST. "
        f"<b>{ok_count}</b> invoice(s) passed all validation checks and <b>{issue_count}</b> "
        f"need attention. Average invoice value was {format_inr(avg_val)}.", S_TEXT
    ))
    story.append(Spacer(1, 8))

    def kpi(label, val):
        return Paragraph(f"{label.upper()}<br/><font size=14 color='#1f3a5f'><b>{val}</b></font>", S_KPI)

    kpis = Table([
        [kpi("Invoices processed", n), kpi("Total invoice value", format_inr(total_value)), kpi("Taxable value", format_inr(taxable_val))],
        [kpi("Total GST", format_inr(total_gst)), kpi("Passed validation", ok_count), kpi("Need attention", issue_count)]
    ], colWidths=[full_w / 3] * 3)
    kpis.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8)
    ]))
    story.append(kpis)

    # GST Breakdown
    tax_rows = [
        ["Tax Component", "Amount"],
        ["CGST", format_inr(cgst_val)],
        ["SGST", format_inr(sgst_val)],
        ["IGST", format_inr(igst_val)],
        ["Total GST", format_inr(total_gst)]
    ]
    tax_table = _grid(tax_rows, [full_w * 0.65, full_w * 0.35], right_cols=(1,), extra=[
        ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"),
        ("LINEABOVE", (0, 4), (-1, 4), 1, NAVY)
    ])
    story.append(KeepTogether([Paragraph("2. GST Breakdown", S_H), tax_table]))

    # Top Vendors Chart & Table
    from collections import defaultdict
    vend_map = defaultdict(lambda: {"count": 0, "value": 0})
    for inv in invoices:
        v_name = inv.party.name if inv.party else "Unknown"
        vend_map[v_name]["count"] += 1
        vend_map[v_name]["value"] += inv.total

    top_vends = sorted([{"vendor": k, **v} for k, v in vend_map.items()], key=lambda x: x["value"], reverse=True)[:5]
    vend_rows = [["Party", "Invoices", "Value", "Share"]]
    for v in top_vends:
        share = (v["value"] / total_value * 100) if total_value else 0
        vend_rows.append([v["vendor"], str(v["count"]), format_inr(v["value"]), f"{share:.1f}%"])

    vend_block = [
        Paragraph("3. Top Parties by Value", S_H),
        _vendor_chart(top_vends, full_w),
        Spacer(1, 6),
        _grid(vend_rows, [full_w * 0.45, full_w * 0.15, full_w * 0.25, full_w * 0.15], right_cols=(1, 2, 3))
    ]
    story.append(KeepTogether(vend_block))

    # Invoice Register
    reg_rows = [["Date", "Invoice No", "Party", "Taxable", "GST", "Total", "Payment"]]
    for inv in invoices:
        p_name = inv.party.name if inv.party else "-"
        reg_rows.append([
            inv.invoice_date.strftime("%d/%m/%Y") if inv.invoice_date else "-",
            inv.invoice_no,
            p_name,
            format_inr(inv.taxable),
            format_inr(inv.cgst + inv.sgst + inv.igst),
            format_inr(inv.total),
            inv.payment_status.capitalize()
        ])
    widths = [22 * mm, 30 * mm, 40 * mm, 28 * mm, 25 * mm, 28 * mm, 20 * mm]
    story.append(KeepTogether([Paragraph("4. Invoice Register", S_H), _grid(reg_rows, widths, right_cols=(3, 4, 5))]))

    def add_company_watermark(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.HexColor("#7a927e"))
        watermark_text = f"{business_name.upper()} • AXION STATUTORY VERIFIED"
        canvas.drawRightString(A4[0] - 15 * mm, 8 * mm, watermark_text)
        canvas.restoreState()

    doc.build(story, onFirstPage=add_company_watermark, onLaterPages=add_company_watermark)
    return buffer.getvalue()
