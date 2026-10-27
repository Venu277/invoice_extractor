from pathlib import Path
from datetime import date
import pytest

from app.extraction.pipeline import process_invoice_extraction
from app.extraction.validate import validate_invoice_data
from app.extraction.reader import PDFCorruptError, read_pdf_content
from app.extraction.fields import parse_date, extract_payment_terms


INVOICES_DIR = Path("invoices")


def test_legacy_sample_invoices():
    """
    Mandatory Section 6 regression requirement:
    - Sharma Traders INV-1001 OK
    - Bright Tech BT/2025/045 OK
    - Mehta Hardware MH-310 (date 15 Mar 2025) OK
    - Sharma Traders INV-1002 OK
    - Kumar Stationery KS-77 flagged for invalid GSTIN and total mismatch
    """
    # 1. inv1.pdf: Sharma Traders INV-1001
    res1 = process_invoice_extraction(INVOICES_DIR / "inv1.pdf", "inv1.pdf")
    f1 = res1["fields"]
    assert "Sharma Traders" in f1["vendor"]
    assert f1["invoice_no"] == "INV-1001"
    assert f1["date"] == date(2025, 3, 12)
    assert f1["supplier_gstin"] == "29ABCDE1234F1Z5"
    assert f1["subtotal"] == 1000000  # 10,000.00 Rs in paise
    assert f1["total"] == 1180000     # 11,800.00 Rs in paise
    # Should have no error severity issues
    errors1 = [i for i in res1["validation_issues"] if i["severity"] == "error"]
    assert len(errors1) == 0

    # 2. inv2.pdf: Bright Tech Solutions BT/2025/045 (CGST + SGST)
    res2 = process_invoice_extraction(INVOICES_DIR / "inv2.pdf", "inv2.pdf")
    f2 = res2["fields"]
    assert "Bright Tech" in f2["vendor"]
    assert f2["invoice_no"] == "BT/2025/045"
    assert f2["date"] == date(2025, 4, 5)
    assert f2["cgst"] == 225000  # 2,250.00 Rs
    assert f2["sgst"] == 225000  # 2,250.00 Rs
    assert f2["total"] == 2950000
    errors2 = [i for i in res2["validation_issues"] if i["severity"] == "error"]
    assert len(errors2) == 0

    # 3. inv3.pdf: Mehta Hardware MH-310 (IGST, date 15 Mar 2025)
    res3 = process_invoice_extraction(INVOICES_DIR / "inv3.pdf", "inv3.pdf")
    f3 = res3["fields"]
    assert "Mehta Hardware" in f3["vendor"]
    assert f3["invoice_no"] == "MH-310"
    assert f3["date"] == date(2025, 3, 15)
    assert f3["igst"] == 720000  # 7,200.00 Rs
    assert f3["total"] == 4720000
    errors3 = [i for i in res3["validation_issues"] if i["severity"] == "error"]
    assert len(errors3) == 0

    # 4. inv5.pdf: Sharma Traders INV-1002
    res5 = process_invoice_extraction(INVOICES_DIR / "inv5.pdf", "inv5.pdf")
    f5 = res5["fields"]
    assert "Sharma Traders" in f5["vendor"]
    assert f5["invoice_no"] == "INV-1002"
    assert f5["date"] == date(2025, 3, 25)
    assert f5["subtotal"] == 1800000
    errors5 = [i for i in res5["validation_issues"] if i["severity"] == "error"]
    assert len(errors5) == 0

    # 5. inv4.pdf: Kumar Stationery KS-77 (invalid GSTIN and total mismatch)
    res4 = process_invoice_extraction(INVOICES_DIR / "inv4.pdf", "inv4.pdf")
    f4 = res4["fields"]
    assert "Kumar Stationery" in f4["vendor"]
    assert f4["invoice_no"] == "KS-77"
    assert res4["validation_status"] == "errors"
    error_codes = [i["code"] for i in res4["validation_issues"] if i["severity"] == "error"]
    assert "INVALID_GSTIN_FORMAT" in error_codes
    assert "TOTAL_MISMATCH" in error_codes


def test_date_parser_variants():
    assert parse_date("12/03/2025") == date(2025, 3, 12)
    assert parse_date("05-04-2025") == date(2025, 4, 5)
    assert parse_date("15.03.2025") == date(2025, 3, 15)
    assert parse_date("15 Mar 2025") == date(2025, 3, 15)
    assert parse_date("2025-04-20") == date(2025, 4, 20)
    assert parse_date("15/03/25") == date(2025, 3, 15)


def test_payment_terms_extractor():
    assert extract_payment_terms("Terms: Net 30 days\nPlease pay promptly.") == "Net 30 days"
    assert extract_payment_terms("Payment Terms: Due in 15 days") == "Due in 15 days"


def test_validation_rule_matrix():
    # Base valid invoice
    valid_inv = {
        "vendor": "Valid Corp",
        "invoice_no": "INV-001",
        "date": date(2025, 1, 1),
        "supplier_gstin": "29ABCDE1234F1Z5",
        "subtotal": 100000,  # Rs. 1000
        "cgst": 9000,        # Rs. 90
        "sgst": 9000,        # Rs. 90
        "igst": 0,
        "cess": 0,
        "total": 118000      # Rs. 1180
    }
    st, issues = validate_invoice_data(valid_inv)
    assert st == "ok"

    # Rule 1: Missing vendor
    inv_bad_vendor = valid_inv.copy()
    inv_bad_vendor["vendor"] = ""
    st, issues = validate_invoice_data(inv_bad_vendor)
    assert st == "errors"
    assert any(i["code"] == "MISSING_VENDOR" for i in issues)

    # Rule 2: CGST and SGST mismatch
    inv_asym = valid_inv.copy()
    inv_asym["cgst"] = 9000
    inv_asym["sgst"] = 0
    st, issues = validate_invoice_data(inv_asym)
    assert st == "errors"
    assert any(i["code"] == "CGST_SGST_ASYMMETRY" for i in issues)

    # Rule 3: IGST conflict with CGST
    inv_conflict = valid_inv.copy()
    inv_conflict["igst"] = 5000
    st, issues = validate_invoice_data(inv_conflict)
    assert st == "errors"
    assert any(i["code"] == "IGST_CONFLICT" for i in issues)

    # Rule 4: Total mismatch
    inv_mismatch = valid_inv.copy()
    inv_mismatch["total"] = 200000  # Rs. 2000 instead of 1180
    st, issues = validate_invoice_data(inv_mismatch)
    assert st == "errors"
    assert any(i["code"] == "TOTAL_MISMATCH" for i in issues)


def test_corrupt_pdf_rejection():
    with pytest.raises(PDFCorruptError):
        read_pdf_content(b"not a real pdf content string")
