import re
from datetime import datetime, date
from decimal import Decimal
from typing import Any
from app.services.money import rupees_to_paise
from app.gst.rules import GSTIN_REGEX, GST_STATE_CODES

AMOUNT_REGEX = r"(?:Rs\.?|INR|₹)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)"

DATE_PATTERNS = [
    # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b",
    # YYYY-MM-DD
    r"\b(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\b",
    # DD Mon YYYY, DD Month YYYY (e.g. 15 Mar 2025, 15 March 2025)
    r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b",
    # DD/MM/YY, DD-MM-YY, DD.MM.YY
    r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})\b"
]

MONTH_NAMES = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
}


def parse_date(text: str) -> date | None:
    """Parses date string day-first into standard date object."""
    if not text:
        return None
    cleaned = text.strip()

    # Try standard string date formats
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
        "%d %b %Y", "%d %B %Y",
        "%Y-%m-%d"
    ]
    # Clean multiple spaces or commas
    norm = re.sub(r"[,\t]+", " ", cleaned)
    norm = re.sub(r"\s+", " ", norm).strip()

    for fmt in formats:
        try:
            return datetime.strptime(norm, fmt).date()
        except ValueError:
            pass

    # Regex based match
    for pat in DATE_PATTERNS:
        m = re.search(pat, cleaned)
        if m:
            groups = m.groups()
            try:
                if len(groups) == 3:
                    if len(groups[0]) == 4:  # YYYY-MM-DD
                        y, m_val, d = int(groups[0]), int(groups[1]), int(groups[2])
                    elif groups[1].lower() in MONTH_NAMES:  # DD Mon YYYY
                        d = int(groups[0])
                        m_val = MONTH_NAMES[groups[1].lower()]
                        y = int(groups[2])
                    else:  # Day first DD MM YYYY or DD MM YY
                        d, m_val = int(groups[0]), int(groups[1])
                        y = int(groups[2])
                        if y < 100:
                            y += 2000
                    return date(y, m_val, d)
            except Exception:
                continue

    return None


def extract_supplier_name(text: str) -> tuple[str | None, str]:
    """
    Supplier name: skip title lines (TAX INVOICE, ORIGINAL FOR RECIPIENT),
    phone, email, address and bill-to lines, and lines starting with a digit.
    """
    skip_keywords = [
        "tax invoice", "invoice", "original for recipient", "duplicate for supplier",
        "triplicate", "bill to", "ship to", "buyer", "consignee", "gstin", "pan",
        "phone", "mobile", "tel", "email", "website", "address", "state", "pincode"
    ]

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        lower = line.lower()
        if any(kw in lower for kw in skip_keywords):
            continue
        if re.match(r"^\d", line):
            continue
        # Looks like a valid company/business name
        if len(line) >= 3:
            return line, "high"

    # Fallback to first non-empty line
    if lines:
        return lines[0], "low"
    return None, "low"


def extract_invoice_number(text: str) -> tuple[str | None, str]:
    # 1. Label with No/Number/#
    m = re.search(r"(?:Invoice|Bill|Inv)\s*(?:No|Number|#|Id)\.?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-_/]*)", text, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        if len(val) >= 2 and not val.lower().startswith("date"):
            return val, "high"

    # 2. Explicit colon or dash delimiter: Invoice: <val>
    m = re.search(r"\b(?:Invoice|Bill|Inv)\s*[:\-]\s*([A-Za-z0-9][A-Za-z0-9\-_/]*)", text, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        if len(val) >= 2 and not val.lower().startswith("date"):
            return val, "medium"

    # 3. Generic #1234 pattern
    m = re.search(r"#\s*([A-Za-z0-9\-_/]+)", text)
    if m:
        return m.group(1).strip(), "medium"

    return None, "low"


def extract_dates(text: str) -> tuple[date | None, str, date | None, str]:
    """Extracts invoice date and due date."""
    inv_date = None
    inv_conf = "low"
    due_date = None
    due_conf = "low"

    # 1. Prefer label 'Invoice Date' over bare 'Date'
    m_inv = re.search(r"Invoice\s*Date\s*[:\-]?\s*([0-9A-Za-z/\-.\s]+)", text, re.IGNORECASE)
    if m_inv:
        d = parse_date(m_inv.group(1))
        if d:
            inv_date, inv_conf = d, "high"

    if not inv_date:
        m_bare = re.search(r"\bDate\s*[:\-]?\s*([0-9A-Za-z/\-.\s]+)", text, re.IGNORECASE)
        if m_bare:
            d = parse_date(m_bare.group(1))
            if d:
                inv_date, inv_conf = d, "medium"

    if not inv_date:
        # Fallback date search
        for line in text.splitlines():
            d = parse_date(line)
            if d:
                inv_date, inv_conf = d, "low"
                break

    # 2. Due Date
    m_due = re.search(r"Due\s*Date\s*[:\-]?\s*([0-9A-Za-z/\-.\s]+)", text, re.IGNORECASE)
    if m_due:
        d = parse_date(m_due.group(1))
        if d:
            due_date, due_conf = d, "high"

    return inv_date, inv_conf, due_date, due_conf


def extract_payment_terms(text: str) -> str | None:
    """Payment terms such as Net 30, Due in 15 days, 30 Days, etc."""
    m = re.search(r"(?:Terms|Payment\s*Terms)\s*[:\-]?\s*([A-Za-z0-9\s]+?)(?:\.|\n|$)", text, re.IGNORECASE)
    if m:
        term = m.group(1).strip()
        if term and len(term) <= 30:
            return term
    m2 = re.search(r"\b(Net\s*\d+|Due\s*(?:in\s*)?\d+\s*days?|\d+\s*days?\s*credit)\b", text, re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    return None


def extract_gstins(text: str) -> tuple[str | None, str, str | None, str]:
    """
    Extracts supplier GSTIN and buyer GSTIN.
    Handles labels like GSTIN, GSTIN No, GSTIN/UIN, and standalone 15-char regex.
    """
    supplier_gstin = None
    buyer_gstin = None
    sup_conf = "low"
    buy_conf = "low"

    # Search labeled buyer lines first
    m_buyer = re.search(r"(?:Buyer|Bill\s*To|Recipient|Customer)\s*(?:[^\n]*\n){0,3}[^\n]*(?:GSTIN|GSTIN/UIN|GST)\s*[:\-]?\s*([0-9A-Za-z]+)", text, re.IGNORECASE)
    if m_buyer:
        buyer_gstin = m_buyer.group(1).upper()
        buy_conf = "high"

    # Labeled supplier lines
    m_sup = re.search(r"(?:Supplier|Seller|Vendor)\s*(?:[^\n]*\n){0,3}[^\n]*(?:GSTIN|GSTIN/UIN|GST)\s*[:\-]?\s*([0-9A-Za-z]+)", text, re.IGNORECASE)
    if m_sup:
        supplier_gstin = m_sup.group(1).upper()
        sup_conf = "high"

    # All labeled GSTINs in order
    labeled = re.findall(r"(?:GSTIN|GSTIN/UIN|GST\s*No|GSTIN\s*No)\.?\s*[:\-]?\s*([0-9A-Za-z]+)", text, re.IGNORECASE)
    for g in labeled:
        g = g.upper()
        if not supplier_gstin:
            supplier_gstin, sup_conf = g, "high"
        elif not buyer_gstin and g != supplier_gstin:
            buyer_gstin, buy_conf = g, "high"

    # Fallback to standalone 15-char GSTIN pattern
    all_gstins = re.findall(r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b", text)
    for g in all_gstins:
        g = g.upper()
        if not supplier_gstin:
            supplier_gstin, sup_conf = g, "medium"
        elif not buyer_gstin and g != supplier_gstin:
            buyer_gstin, buy_conf = g, "medium"

    return supplier_gstin, sup_conf, buyer_gstin, buy_conf


def extract_place_of_supply(text: str) -> str | None:
    """Extracts place of supply state code (e.g. '29' or state name matched to code)."""
    m = re.search(r"Place\s*of\s*Supply\s*[:\-]?\s*([A-Za-z0-9\s\-]+?)(?:\.|\n|,|$)", text, re.IGNORECASE)
    if m:
        pos_raw = m.group(1).strip()
        # Check if digits
        code_match = re.search(r"\b(\d{2})\b", pos_raw)
        if code_match and code_match.group(1) in GST_STATE_CODES:
            return code_match.group(1)
        # Check state name
        for code, name in GST_STATE_CODES.items():
            if name.lower() in pos_raw.lower():
                return code

    # Check "State: Karnataka" or "State Code: 29"
    m_state = re.search(r"State\s*(?:Code)?\s*[:\-]?\s*([A-Za-z0-9\s]+?)(?:\.|\n|,|$)", text, re.IGNORECASE)
    if m_state:
        st_raw = m_state.group(1).strip()
        code_match = re.search(r"\b(\d{2})\b", st_raw)
        if code_match and code_match.group(1) in GST_STATE_CODES:
            return code_match.group(1)
        for code, name in GST_STATE_CODES.items():
            if name.lower() in st_raw.lower():
                return code

    return None


def extract_amount_by_labels(labels: list[str], text: str) -> tuple[int | None, str]:
    """Finds amount for given labels, returns (paise, confidence)."""
    for label in labels:
        matches = re.findall(label + r"\s*[:\-]?\s*" + AMOUNT_REGEX, text, re.IGNORECASE)
        if matches:
            return rupees_to_paise(matches[-1]), "high"

    # Line by line check (e.g. label on line, number on next line)
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        for label in labels:
            if re.search(r"\b" + label + r"\b", line, re.IGNORECASE):
                # Check same line
                nums = re.findall(AMOUNT_REGEX, line)
                if nums:
                    return rupees_to_paise(nums[-1]), "high"
                # Check next line if it is just a number
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1].strip()
                    if re.match(r"^(?:Rs\.?|INR|₹)?\s*\d[\d,]*(?:\.\d{1,2})?$", next_line):
                        return rupees_to_paise(next_line), "medium"

    return None, "low"


def extract_tax_by_label(label: str, text: str) -> tuple[int | None, str]:
    """Extracts tax component (CGST, SGST, IGST, CESS, or general GST), ignoring rates/percentages."""
    for line in text.splitlines():
        if not re.search(r"\b" + label + r"\b", line, re.IGNORECASE):
            continue
        # Skip lines that are GSTIN identifiers
        if re.search(r"GST\s*(?:IN|No|Number|Reg|UIN)", line, re.IGNORECASE):
            continue

        # Remove percentage expressions like 9%, 18%, 2.5%
        clean_line = re.sub(r"\d+(?:\.\d+)?\s*%", " ", line)
        # Remove the label itself
        clean_line = re.sub(label, " ", clean_line, flags=re.IGNORECASE)

        # Extract remaining amount numbers
        numbers = re.findall(r"\d[\d,]*(?:\.\d{1,2})?", clean_line)
        if numbers:
            return rupees_to_paise(numbers[-1]), "high"

    return None, "low"


def extract_all_fields(text: str, business_gstin: str | None = None) -> dict[str, Any]:
    """
    Performs complete field extraction, confidence scoring, and direction classification.
    All monetary fields returned as integer paise.
    """
    confidences = {}

    supplier, s_conf = extract_supplier_name(text)
    confidences["vendor"] = s_conf

    invoice_no, i_conf = extract_invoice_number(text)
    confidences["invoice_no"] = i_conf

    inv_date, d_conf, due_date, due_conf = extract_dates(text)
    confidences["date"] = d_conf
    confidences["due_date"] = due_conf

    payment_terms = extract_payment_terms(text)

    sup_gstin, sg_conf, buy_gstin, bg_conf = extract_gstins(text)
    confidences["supplier_gstin"] = sg_conf
    confidences["buyer_gstin"] = bg_conf

    place_of_supply = extract_place_of_supply(text)

    # Taxable / Subtotal
    subtotal, sub_conf = extract_amount_by_labels(
        [r"Sub\s*total", r"Taxable\s*Value", r"Taxable\s*Amount"], text
    )
    confidences["subtotal"] = sub_conf

    # Tax components
    cgst, cgst_conf = extract_tax_by_label("CGST", text)
    sgst, sgst_conf = extract_tax_by_label("SGST", text)
    igst, igst_conf = extract_tax_by_label("IGST", text)
    cess, cess_conf = extract_tax_by_label("CESS", text)

    # General GST line if CGST/SGST/IGST not present
    gst_general, gst_conf = extract_tax_by_label("GST", text)

    # Total / Grand Total
    total, tot_conf = extract_amount_by_labels(
        [r"Grand\s*Total", r"Total\s*Amount", r"Total\s*Invoice\s*Value",
         r"Net\s*Payable", r"Amount\s*Due", r"\bTotal\b"], text
    )
    confidences["total"] = tot_conf

    # Classify direction
    direction = "unknown"
    if business_gstin:
        bg = business_gstin.strip().upper()
        if buy_gstin and buy_gstin.upper() == bg:
            direction = "purchase"
        elif sup_gstin and sup_gstin.upper() == bg:
            direction = "sales"

    return {
        "vendor": supplier,
        "invoice_no": invoice_no,
        "date": inv_date,
        "due_date": due_date,
        "payment_terms": payment_terms,
        "supplier_gstin": sup_gstin,
        "buyer_gstin": buy_gstin,
        "place_of_supply": place_of_supply,
        "subtotal": subtotal or 0,
        "cgst": cgst or 0,
        "sgst": sgst or 0,
        "igst": igst or 0,
        "cess": cess or 0,
        "gst_general": gst_general or 0,
        "total": total or 0,
        "direction": direction,
        "confidence": confidences
    }
