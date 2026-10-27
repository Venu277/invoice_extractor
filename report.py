"""Builds the professional monthly business summary report as a PDF (in memory)."""
import io
from datetime import datetime
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

NAVY = colors.HexColor("#1f3a5f")
LIGHT = colors.HexColor("#f3f4f6")
LINE = colors.HexColor("#c9ced6")
RED_BG = colors.HexColor("#fdecea")
GREEN = colors.HexColor("#1e7e46")
RED = colors.HexColor("#b3261e")

_base = getSampleStyleSheet()["Normal"]
S_TEXT = ParagraphStyle("t", parent=_base, fontName="Helvetica", fontSize=9.5, leading=13)
S_H = ParagraphStyle("h", parent=_base, fontName="Helvetica-Bold", fontSize=12.5,
                     textColor=NAVY, spaceBefore=14, spaceAfter=6)
S_CELL = ParagraphStyle("c", parent=_base, fontName="Helvetica", fontSize=8.3, leading=10.5)
S_CELL_R = ParagraphStyle("cr", parent=S_CELL, alignment=2)
S_HEAD = ParagraphStyle("hd", parent=S_CELL, fontName="Helvetica-Bold", textColor=colors.white)
S_HEAD_R = ParagraphStyle("hdr", parent=S_HEAD, alignment=2)
S_BANNER1 = ParagraphStyle("b1", parent=_base, fontName="Helvetica-Bold", fontSize=20,
                           leading=24, textColor=colors.white)
S_BANNER2 = ParagraphStyle("b2", parent=_base, fontName="Helvetica", fontSize=11,
                           leading=15, textColor=colors.white)
S_KPI = ParagraphStyle("k", parent=_base, fontName="Helvetica", fontSize=8, leading=14,
                       textColor=colors.HexColor("#555555"))


def month_label(month_key):
    return datetime.strptime(month_key + "-01", "%Y-%m-%d").strftime("%B %Y")


def money(x):
    return "-" if x is None or pd.isna(x) else f"{x:,.2f}"


def esc(x):
    return "-" if x is None or (not isinstance(x, str) and pd.isna(x)) else escape(str(x))


def _grid(rows, widths, right_cols=(), header_bg=NAVY, extra=None):
    data = []
    for r, row in enumerate(rows):
        line = []
        for c, value in enumerate(row):
            if r == 0:
                style = S_HEAD_R if c in right_cols else S_HEAD
            else:
                style = S_CELL_R if c in right_cols else S_CELL
            line.append(Paragraph(esc(value), style))
        data.append(line)
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), header_bg),
             ("GRID", (0, 0), (-1, -1), 0.4, LINE),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
             ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    if extra:
        style += extra
    t.setStyle(TableStyle(style))
    return t


def _vendor_chart(vendors, width):
    """Simple horizontal bar chart drawn with basic shapes."""
    row_h = 20
    d = Drawing(width, row_h * len(vendors) + 4)
    biggest = max(v["value"] for v in vendors) or 1
    label_w, bar_max = 150, width - 150 - 90
    for i, v in enumerate(vendors):
        y = (len(vendors) - 1 - i) * row_h + 4
        name = v["vendor"] if len(v["vendor"]) <= 28 else v["vendor"][:26] + ".."
        d.add(String(0, y + 4, name, fontName="Helvetica", fontSize=8.5,
                     fillColor=colors.HexColor("#333333")))
        bar = max(2, bar_max * v["value"] / biggest)
        d.add(Rect(label_w, y, bar, 12, fillColor=NAVY, strokeColor=None))
        d.add(String(label_w + bar + 6, y + 3, f"Rs. {v['value']:,.0f}", fontName="Helvetica",
                     fontSize=8, fillColor=colors.HexColor("#333333")))
    return d


def build_report(business_name, month_key, df):
    """df = the user's invoices for ONE month. Returns the PDF as bytes."""
    df = df.copy()
    for col in ["subtotal", "cgst", "sgst", "igst", "gst_amount", "total"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["vendor"] = df["vendor"].fillna("Unknown vendor")

    n = len(df)
    total_value = df["total"].sum()
    taxable = df["subtotal"].sum()
    total_gst = df["gst_amount"].sum()
    ok_count = int((df["status"] == "OK").sum())
    issue_count = n - ok_count
    cgst, sgst, igst = df["cgst"].sum(), df["sgst"].sum(), df["igst"].sum()
    other_gst = round(total_gst - cgst - sgst - igst, 2)

    buffer = io.BytesIO()
    period = month_label(month_key)
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=18 * mm,
                            title=f"Monthly Invoice Summary - {period}", author=business_name)
    full_w = A4[0] - 30 * mm
    story = []

    # ---- Banner ----
    banner = Table([[Paragraph(esc(business_name), S_BANNER1)],
                    [Paragraph(f"Monthly Invoice Summary Report &nbsp;|&nbsp; {period}", S_BANNER2)]],
                   colWidths=[full_w])
    banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY),
                                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                                ("TOPPADDING", (0, 0), (0, 0), 14),
                                ("BOTTOMPADDING", (0, 1), (0, 1), 14)]))
    story += [banner, Spacer(1, 12)]

    # ---- Executive summary ----
    story.append(Paragraph("1. Executive Summary", S_H))
    avg = total_value / n if n else 0
    story.append(Paragraph(
        f"During {period}, <b>{n}</b> invoice(s) were processed with a combined value of "
        f"<b>Rs. {total_value:,.2f}</b>, of which <b>Rs. {total_gst:,.2f}</b> is GST. "
        f"<b>{ok_count}</b> invoice(s) passed all validation checks and <b>{issue_count}</b> "
        f"need attention. The average invoice value was Rs. {avg:,.2f}.", S_TEXT))
    story.append(Spacer(1, 6))

    def kpi(label, value):
        return Paragraph(f"{label.upper()}<br/><font size=15 color='#1f3a5f'><b>{value}</b></font>",
                         S_KPI)

    kpis = Table([[kpi("Invoices processed", n), kpi("Total invoice value", f"Rs. {total_value:,.0f}"),
                   kpi("Taxable value", f"Rs. {taxable:,.0f}")],
                  [kpi("Total GST", f"Rs. {total_gst:,.0f}"), kpi("Passed validation", ok_count),
                   kpi("Need attention", issue_count)]],
                 colWidths=[full_w / 3] * 3)
    kpis.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINE),
                              ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                              ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                              ("TOPPADDING", (0, 0), (-1, -1), 8),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                              ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    story.append(kpis)

    # ---- Tax breakdown ----
    tax_rows = [["Tax component", "Amount (Rs.)"],
                ["CGST", money(cgst)], ["SGST", money(sgst)], ["IGST", money(igst)],
                ["Other / combined GST (single-line invoices)", money(max(other_gst, 0))],
                ["Total GST", money(total_gst)]]
    tax_table = _grid(tax_rows, [full_w * 0.65, full_w * 0.35], right_cols=(1,),
                      extra=[("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold"),
                             ("LINEABOVE", (0, 5), (-1, 5), 1, NAVY)])
    story.append(KeepTogether([Paragraph("2. GST Breakdown", S_H), tax_table]))

    # ---- Top vendors ----
    grouped = (df.groupby("vendor").agg(count=("vendor", "size"), value=("total", "sum"))
                 .sort_values("value", ascending=False).head(5).reset_index())
    vendors = [{"vendor": r["vendor"], "count": int(r["count"]), "value": float(r["value"])}
               for _, r in grouped.iterrows()]
    vend_rows = [["Vendor", "Invoices", "Value (Rs.)", "Share"]]
    for v in vendors:
        share = (v["value"] / total_value * 100) if total_value else 0
        vend_rows.append([v["vendor"], str(v["count"]), money(v["value"]), f"{share:.1f}%"])
    vend_block = [Paragraph("3. Top Vendors by Value", S_H),
                  _vendor_chart(vendors, full_w), Spacer(1, 6),
                  _grid(vend_rows, [full_w * 0.45, full_w * 0.13, full_w * 0.27, full_w * 0.15],
                        right_cols=(1, 2, 3))]
    story.append(KeepTogether(vend_block))

    # ---- Invoice register ----
    reg = df.sort_values(["date", "invoice_no"], na_position="last")
    reg_rows = [["Date", "Invoice No", "Vendor", "Taxable (Rs.)", "GST (Rs.)", "Total (Rs.)", "Status"]]
    extra = []
    for i, (_, r) in enumerate(reg.iterrows(), start=1):
        is_ok = r["status"] == "OK"
        reg_rows.append([r["date"], r["invoice_no"], r["vendor"], money(r["subtotal"]),
                         money(r["gst_amount"]), money(r["total"]), "OK" if is_ok else "Issue"])
        if not is_ok:
            extra.append(("BACKGROUND", (0, i), (-1, i), RED_BG))
    reg_rows.append(["", "", "Total", money(taxable), money(total_gst), money(total_value), ""])
    last = len(reg_rows) - 1
    extra += [("FONTNAME", (0, last), (-1, last), "Helvetica-Bold"),
              ("LINEABOVE", (0, last), (-1, last), 1, NAVY),
              ("BACKGROUND", (0, last), (-1, last), colors.white)]
    widths = [20 * mm, 28 * mm, 42 * mm, 26 * mm, 22 * mm, 26 * mm, 16 * mm]
    story.append(Paragraph("4. Invoice Register", S_H))
    story.append(_grid(reg_rows, widths, right_cols=(3, 4, 5), extra=extra))

    # ---- Needs attention ----
    bad = reg[reg["status"] != "OK"]
    story.append(Paragraph("5. Items Needing Attention", S_H))
    if bad.empty:
        story.append(Paragraph("All invoices for this month passed validation. No action required.",
                               S_TEXT))
    else:
        att = [["Invoice No", "Vendor", "Issue found"]]
        for _, r in bad.iterrows():
            att.append([r["invoice_no"], r["vendor"], r["status"]])
        story.append(_grid(att, [30 * mm, 50 * mm, full_w - 80 * mm]))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Figures are extracted automatically from the uploaded invoice PDFs and checked against "
        "basic GST rules (GSTIN format, CGST = SGST, subtotal + tax = total). Please review "
        "flagged items before filing returns.", ParagraphStyle("note", parent=S_TEXT, fontSize=8,
                                                              textColor=colors.HexColor("#666666"))))

    generated = datetime.now().strftime("%d %b %Y, %H:%M")

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(15 * mm, 10 * mm, f"{business_name} | {period} | Generated {generated}")
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()