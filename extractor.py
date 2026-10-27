import os
import re
import csv
from datetime import datetime

import pdfplumber
from PyPDF2 import PdfReader

INPUT_FOLDER = "invoices"
OUTPUT_FILE = os.path.join("output", "invoices.csv")


def read_with_pdfplumber(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    return text


def read_with_pypdf2(path):
    reader = PdfReader(path)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def read_with_ocr(path):
    """OPTIONAL (extension): for scanned invoices. Needs Tesseract + Poppler."""
    from pdf2image import convert_from_path
    import pytesseract
    pages = convert_from_path(path)
    return "\n".join(pytesseract.image_to_string(p) for p in pages)


def read_pdf_text(path):
    text = read_with_pdfplumber(path)
    if not text.strip():
        text = read_with_pypdf2(path)
    if not text.strip():
        try:
            text = read_with_ocr(path)
        except Exception:
            text = ""
    return text


AMOUNT = r"(?:Rs\.?|INR)?\s*(\d[\d,]*(?:\.\d{1,2})?)"
DATE = (r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
        r"|\d{1,2}\s+[A-Za-z]{3,9}\.?,?\s+\d{4})")

DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
                "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
                "%d %b %Y", "%d %B %Y"]


def to_float(number_text):
    return float(number_text.replace(",", ""))


def standardise_date(date_text):
    if not date_text:
        return None
    cleaned = date_text.strip()
    if re.search(r"[A-Za-z]", cleaned):
        cleaned = re.sub(r"[.,]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_text


def find_amount(labels, text):
    for label in labels:
        matches = re.findall(label + r"\s*[:\-]?\s*" + AMOUNT, text, re.IGNORECASE)
        if matches:
            return to_float(matches[-1])
    return None


def find_tax(label, text):
    found = None
    for line in text.splitlines():
        if not re.search(label, line, re.IGNORECASE):
            continue
        if re.search(r"GST\s*(?:IN|No|Number|Reg)", line, re.IGNORECASE):
            continue
        line = re.sub(r"\d+(?:\.\d+)?\s*%", " ", line)
        line = re.sub(label, " ", line, flags=re.IGNORECASE)
        numbers = re.findall(r"\d[\d,]*(?:\.\d{1,2})?", line)
        if numbers:
            found = to_float(numbers[-1])
    return found


def find_vendor(text):
    for line in text.splitlines():
        line = line.strip()
        if line and "invoice" not in line.lower():
            return line
    return None


def extract_fields(text):
    data = {}
    data["vendor"] = find_vendor(text)

    m = re.search(r"Invoice\s*(?:No|Number|#)\.?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-/]*)",
                  text, re.IGNORECASE)
    data["invoice_no"] = m.group(1) if m else None

    m = re.search(r"\bDate\b\s*[:\-]?\s*" + DATE, text, re.IGNORECASE)
    if not m:
        m = re.search(DATE, text)
    data["date"] = standardise_date(m.group(1)) if m else None

    m = re.search(r"GSTIN\s*[:\-]?\s*([A-Z0-9]+)", text, re.IGNORECASE)
    data["gstin"] = m.group(1).upper() if m else None

    data["subtotal"] = find_amount([r"Sub\s*total"], text)

    data["cgst"] = find_tax(r"\bCGST\b", text)
    data["sgst"] = find_tax(r"\bSGST\b", text)
    data["igst"] = find_tax(r"\bIGST\b", text)

    parts = [x for x in (data["cgst"], data["sgst"], data["igst"]) if x is not None]
    if parts:
        data["gst_amount"] = round(sum(parts), 2)
    else:
        data["gst_amount"] = find_tax(r"\bGST\b", text)

    data["total"] = find_amount(
        [r"Grand\s*Total", r"Total\s*Amount", r"Amount\s*Due", r"\bTotal"], text)
    return data


GSTIN_PATTERN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]")


def validate(data):
    issues = []
    for field in ["vendor", "invoice_no", "date", "total"]:
        if not data[field]:
            issues.append(f"{field} missing")

    if not data["gstin"]:
        issues.append("GSTIN missing")
    elif not GSTIN_PATTERN.fullmatch(data["gstin"]):
        issues.append("GSTIN invalid")

    cgst, sgst, igst = data["cgst"], data["sgst"], data["igst"]
    if (cgst is None) != (sgst is None):
        issues.append("CGST/SGST incomplete (one is missing)")
    if cgst is not None and sgst is not None and abs(cgst - sgst) > 0.01:
        issues.append("CGST and SGST differ")
    if igst and (cgst or sgst):
        issues.append("IGST present with CGST/SGST")

    sub, gst, total = data["subtotal"], data["gst_amount"], data["total"]
    if sub is not None and gst is not None and total is not None:
        if abs((sub + gst) - total) > 0.01:
            issues.append("Total mismatch (subtotal + GST != total)")

    return "OK" if not issues else "; ".join(issues)


COLUMNS = ["file", "vendor", "invoice_no", "date", "gstin",
           "subtotal", "cgst", "sgst", "igst", "gst_amount", "total", "status"]