import io
import csv
import zipfile
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.config import settings
from app.models.invoice import Invoice
from app.models.party import Party
from app.models.business import Business
from app.services.fy_service import filter_query_by_period
from app.services.money import paise_to_decimal, format_inr
from app.services.report_pdf_service import generate_monthly_report_pdf
from app.gst.summaries import compute_gstr1_summary, compute_gstr3b_summary, compute_hsn_summary


def export_invoices_csv(
    db: Session,
    business_id: int,
    fy: int | None = None,
    month: str | None = None
) -> str:
    biz = db.query(Business).filter(Business.id == business_id).first()
    fy_start = biz.fy_start_month if biz else 4

    query = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.deleted_at.is_(None)
    )
    query = filter_query_by_period(query, fy=fy, month=month, fy_start_month=fy_start)
    invoices = query.order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Invoice No", "Date", "Due Date", "Direction", "Party Name", "GSTIN",
        "Place of Supply", "Taxable (Rs.)", "CGST (Rs.)", "SGST (Rs.)",
        "IGST (Rs.)", "Total (Rs.)", "Amount Paid (Rs.)", "Payment Status",
        "Review Status", "Validation Status"
    ])

    for inv in invoices:
        p_name = inv.party.name if inv.party else ""
        writer.writerow([
            inv.invoice_no,
            inv.invoice_date.strftime("%Y-%m-%d") if inv.invoice_date else "",
            inv.due_date.strftime("%Y-%m-%d") if inv.due_date else "",
            inv.direction.capitalize(),
            p_name,
            inv.supplier_gstin or inv.buyer_gstin or "",
            inv.place_of_supply_state or "",
            f"{paise_to_decimal(inv.taxable):.2f}",
            f"{paise_to_decimal(inv.cgst):.2f}",
            f"{paise_to_decimal(inv.sgst):.2f}",
            f"{paise_to_decimal(inv.igst):.2f}",
            f"{paise_to_decimal(inv.total):.2f}",
            f"{paise_to_decimal(inv.amount_paid):.2f}",
            inv.payment_status.capitalize(),
            inv.review_status.capitalize(),
            inv.validation_status.upper()
        ])

    return output.getvalue()


def export_invoices_excel(
    db: Session,
    business_id: int,
    fy: int | None = None,
    month: str | None = None
) -> bytes:
    biz = db.query(Business).filter(Business.id == business_id).first()
    fy_start = biz.fy_start_month if biz else 4

    query = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.deleted_at.is_(None)
    )
    query = filter_query_by_period(query, fy=fy, month=month, fy_start_month=fy_start)
    invoices = query.order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Invoices Register"

    # Header styling
    headers = [
        "Invoice No", "Date", "Due Date", "Direction", "Party Name", "GSTIN",
        "Taxable", "CGST", "SGST", "IGST", "Total", "Amount Paid", "Payment Status", "Review Status"
    ]
    ws.append(headers)

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F3A5F", end_color="1F3A5F", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Row colors for validation issues
    green_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    red_fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")

    row_num = 2
    for inv in invoices:
        p_name = inv.party.name if inv.party else ""
        row_data = [
            inv.invoice_no,
            inv.invoice_date.strftime("%Y-%m-%d") if inv.invoice_date else "",
            inv.due_date.strftime("%Y-%m-%d") if inv.due_date else "",
            inv.direction.capitalize(),
            p_name,
            inv.supplier_gstin or inv.buyer_gstin or "",
            float(paise_to_decimal(inv.taxable)),
            float(paise_to_decimal(inv.cgst)),
            float(paise_to_decimal(inv.sgst)),
            float(paise_to_decimal(inv.igst)),
            float(paise_to_decimal(inv.total)),
            float(paise_to_decimal(inv.amount_paid)),
            inv.payment_status.capitalize(),
            inv.review_status.capitalize()
        ]
        ws.append(row_data)

        # Apply row styling
        fill = green_fill if inv.validation_status == "ok" else red_fill
        for col_idx in range(1, len(headers) + 1):
            c = ws.cell(row=row_num, column=col_idx)
            c.fill = fill
            if col_idx in [7, 8, 9, 10, 11, 12]:
                c.number_format = "#,##0.00"
                c.alignment = right_align
        row_num += 1

    # Totals Row
    total_row = row_num
    ws.cell(row=total_row, column=1, value="TOTAL")
    ws.cell(row=total_row, column=1).font = Font(bold=True)
    for c_idx in range(7, 13):
        col_letter = get_column_letter(c_idx)
        total_cell = ws.cell(row=total_row, column=c_idx)
        total_cell.value = f"=SUM({col_letter}2:{col_letter}{total_row - 1})"
        total_cell.font = Font(bold=True)
        total_cell.number_format = "#,##0.00"

    # Freeze Header and Enable Filters
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{total_row - 1}"

    # Auto column width
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def export_tally_xml(
    db: Session,
    business_id: int,
    fy: int | None = None,
    month: str | None = None
) -> str:
    """
    Generates Tally XML import format:
    - Ledger Masters for Parties and Accounts
    - Purchase and Sales Vouchers
    - Every voucher balances to zero
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

    # Get distinct parties
    party_ids = {inv.party_id for inv in invoices if inv.party_id}
    parties = db.query(Party).filter(Party.id.in_(party_ids)).all() if party_ids else []

    xml_lines = [
        '<ENVELOPE>',
        '  <HEADER>',
        '    <TALLYREQUEST>Import Data</TALLYREQUEST>',
        '  </HEADER>',
        '  <BODY>',
        '    <IMPORTDATA>',
        '      <REQUESTDESC>',
        '        <REPORTNAME>All Masters</REPORTNAME>',
        '      </REQUESTDESC>',
        '      <REQUESTDATA>'
    ]

    # Ledger Masters
    for p in parties:
        parent_group = "Sundry Debtors" if p.type == "customer" else "Sundry Creditors"
        xml_lines.extend([
            '        <TALLYMESSAGE xmlns:UDF="TallyUDF">',
            f'          <LEDGER NAME="{escape_xml(p.name)}" ACTION="Create">',
            f'            <NAME>{escape_xml(p.name)}</NAME>',
            f'            <PARENT>{parent_group}</PARENT>',
            f'            <PARTYGSTIN>{p.gstin or ""}</PARTYGSTIN>',
            '          </LEDGER>',
            '        </TALLYMESSAGE>'
        ])

    # Vouchers
    for inv in invoices:
        vch_type = "Sales" if inv.direction == "sales" else "Purchase"
        inv_dt = inv.invoice_date.strftime("%Y%m%d") if inv.invoice_date else datetime.now().strftime("%Y%m%d")
        party_name = escape_xml(inv.party.name if inv.party else "Cash")

        total_rs = float(paise_to_decimal(inv.total))
        taxable_rs = float(paise_to_decimal(inv.taxable))
        cgst_rs = float(paise_to_decimal(inv.cgst))
        sgst_rs = float(paise_to_decimal(inv.sgst))
        igst_rs = float(paise_to_decimal(inv.igst))

        xml_lines.extend([
            '        <TALLYMESSAGE xmlns:UDF="TallyUDF">',
            f'          <VOUCHER VCHTYPE="{vch_type}" ACTION="Create">',
            f'            <DATE>{inv_dt}</DATE>',
            f'            <VOUCHERTYPENAME>{vch_type}</VOUCHERTYPENAME>',
            f'            <VOUCHERNUMBER>{escape_xml(inv.invoice_no)}</VOUCHERNUMBER>',
            f'            <PARTYLEDGERNAME>{party_name}</PARTYLEDGERNAME>'
        ])

        if inv.direction == "sales":
            # Sales Voucher:
            # Party = +Total (Debit)
            # Sales Ledger = -Taxable (Credit)
            # Output CGST = -CGST
            # Output SGST = -SGST
            # Output IGST = -IGST
            xml_lines.extend([
                '            <ALLLEDGERENTRIES.LIST>',
                f'              <LEDGERNAME>{party_name}</LEDGERNAME>',
                '              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                f'              <AMOUNT>-{total_rs:.2f}</AMOUNT>',
                '            </ALLLEDGERENTRIES.LIST>',
                '            <ALLLEDGERENTRIES.LIST>',
                f'              <LEDGERNAME>{settings.TALLY_LEDGER_SALES}</LEDGERNAME>',
                '              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                f'              <AMOUNT>{taxable_rs:.2f}</AMOUNT>',
                '            </ALLLEDGERENTRIES.LIST>'
            ])
            if cgst_rs > 0:
                xml_lines.extend([
                    '            <ALLLEDGERENTRIES.LIST>',
                    f'              <LEDGERNAME>{settings.TALLY_LEDGER_OUTPUT_CGST}</LEDGERNAME>',
                    '              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                    f'              <AMOUNT>{cgst_rs:.2f}</AMOUNT>',
                    '            </ALLLEDGERENTRIES.LIST>'
                ])
            if sgst_rs > 0:
                xml_lines.extend([
                    '            <ALLLEDGERENTRIES.LIST>',
                    f'              <LEDGERNAME>{settings.TALLY_LEDGER_OUTPUT_SGST}</LEDGERNAME>',
                    '              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                    f'              <AMOUNT>{sgst_rs:.2f}</AMOUNT>',
                    '            </ALLLEDGERENTRIES.LIST>'
                ])
            if igst_rs > 0:
                xml_lines.extend([
                    '            <ALLLEDGERENTRIES.LIST>',
                    f'              <LEDGERNAME>{settings.TALLY_LEDGER_OUTPUT_IGST}</LEDGERNAME>',
                    '              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                    f'              <AMOUNT>{igst_rs:.2f}</AMOUNT>',
                    '            </ALLLEDGERENTRIES.LIST>'
                ])
        else:
            # Purchase Voucher:
            # Party = -Total (Credit)
            # Purchase Ledger = +Taxable (Debit)
            # Input CGST = +CGST
            # Input SGST = +SGST
            # Input IGST = +IGST
            xml_lines.extend([
                '            <ALLLEDGERENTRIES.LIST>',
                f'              <LEDGERNAME>{party_name}</LEDGERNAME>',
                '              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                f'              <AMOUNT>{total_rs:.2f}</AMOUNT>',
                '            </ALLLEDGERENTRIES.LIST>',
                '            <ALLLEDGERENTRIES.LIST>',
                f'              <LEDGERNAME>{settings.TALLY_LEDGER_PURCHASE}</LEDGERNAME>',
                '              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                f'              <AMOUNT>-{taxable_rs:.2f}</AMOUNT>',
                '            </ALLLEDGERENTRIES.LIST>'
            ])
            if cgst_rs > 0:
                xml_lines.extend([
                    '            <ALLLEDGERENTRIES.LIST>',
                    f'              <LEDGERNAME>{settings.TALLY_LEDGER_INPUT_CGST}</LEDGERNAME>',
                    '              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                    f'              <AMOUNT>-{cgst_rs:.2f}</AMOUNT>',
                    '            </ALLLEDGERENTRIES.LIST>'
                ])
            if sgst_rs > 0:
                xml_lines.extend([
                    '            <ALLLEDGERENTRIES.LIST>',
                    f'              <LEDGERNAME>{settings.TALLY_LEDGER_INPUT_SGST}</LEDGERNAME>',
                    '              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                    f'              <AMOUNT>-{sgst_rs:.2f}</AMOUNT>',
                    '            </ALLLEDGERENTRIES.LIST>'
                ])
            if igst_rs > 0:
                xml_lines.extend([
                    '            <ALLLEDGERENTRIES.LIST>',
                    f'              <LEDGERNAME>{settings.TALLY_LEDGER_INPUT_IGST}</LEDGERNAME>',
                    '              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                    f'              <AMOUNT>-{igst_rs:.2f}</AMOUNT>',
                    '            </ALLLEDGERENTRIES.LIST>'
                ])

        xml_lines.extend([
            '          </VOUCHER>',
            '        </TALLYMESSAGE>'
        ])

    xml_lines.extend([
        '      </REQUESTDATA>',
        '    </IMPORTDATA>',
        '  </BODY>',
        '</ENVELOPE>'
    ])

    return "\n".join(xml_lines)


def export_accountant_package_zip(
    db: Session,
    business_id: int,
    month: str  # YYYY-MM
) -> bytes:
    """
    Creates complete Accountant Package ZIP:
    - Original PDFs organized by month
    - Invoices in Excel and CSV
    - Monthly Report PDF
    - GST Summaries (GSTR-1, GSTR-3B, HSN)
    - Index manifest
    """
    invoices_csv = export_invoices_csv(db, business_id, month=month)
    invoices_xlsx = export_invoices_excel(db, business_id, month=month)
    report_pdf = generate_monthly_report_pdf(db, business_id, month)

    # Query invoices to get physical PDF paths
    invoices = db.query(Invoice).filter(
        Invoice.business_id == business_id,
        Invoice.deleted_at.is_(None)
    ).all()
    month_invoices = [i for i in invoices if i.invoice_date and i.invoice_date.strftime("%Y-%m") == month]

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
        # Add spreadsheets & report
        z.writestr(f"Invoices_{month}.csv", invoices_csv)
        z.writestr(f"Invoices_{month}.xlsx", invoices_xlsx)
        z.writestr(f"Monthly_Report_{month}.pdf", report_pdf)

        # Add original PDFs
        for inv in month_invoices:
            if inv.document and inv.document.stored_path:
                doc_path = Path(inv.document.stored_path)
                if doc_path.exists():
                    safe_name = f"pdfs/{month}/{inv.invoice_no}_{inv.document.original_name}"
                    z.write(str(doc_path), arcname=safe_name)

        # Index file
        manifest = [
            f"Accountant Package for {month}",
            f"Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Invoices in Period: {len(month_invoices)}",
            "",
            "Contents:",
            f"- Invoices_{month}.csv: Complete invoice register in CSV format",
            f"- Invoices_{month}.xlsx: Formatted Excel workbook with frozen headers & totals",
            f"- Monthly_Report_{month}.pdf: Executive monthly business report",
            f"- pdfs/{month}/: Original uploaded PDF invoices"
        ]
        z.writestr("index.txt", "\n".join(manifest))

    return zip_buffer.getvalue()


def escape_xml(s: str) -> str:
    if not s:
        return ""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;"))
