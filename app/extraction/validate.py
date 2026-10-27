from typing import Any
from decimal import Decimal
from app.gst.rules import is_valid_gstin_format, get_gstin_state_code, STANDARD_GST_RATES


def validate_invoice_data(
    data: dict[str, Any],
    business_state_code: str | None = None
) -> tuple[str, list[dict[str, str]]]:
    """
    Validates invoice fields according to statutory GST rules and arithmetic integrity.
    Each issue contains: {code, field, message, severity: 'error' | 'warning'}.
    Returns (status, issues_list), where status is 'ok', 'warnings', or 'errors'.
    """
    issues: list[dict[str, str]] = []

    # 1. Missing mandatory fields (error)
    if not data.get("vendor"):
        issues.append({
            "code": "MISSING_VENDOR",
            "field": "vendor",
            "message": "Supplier / Vendor name is missing.",
            "severity": "error"
        })

    if not data.get("invoice_no"):
        issues.append({
            "code": "MISSING_INVOICE_NO",
            "field": "invoice_no",
            "message": "Invoice number is missing.",
            "severity": "error"
        })

    if not data.get("date"):
        issues.append({
            "code": "MISSING_DATE",
            "field": "date",
            "message": "Invoice date is missing or unparseable.",
            "severity": "error"
        })

    total_paise = data.get("total") or 0
    if total_paise <= 0:
        issues.append({
            "code": "MISSING_OR_ZERO_TOTAL",
            "field": "total",
            "message": "Invoice total amount is missing or zero.",
            "severity": "error"
        })

    # 2. GSTIN Validation
    gstin = data.get("supplier_gstin") or data.get("gstin")
    if not gstin:
        issues.append({
            "code": "MISSING_GSTIN",
            "field": "supplier_gstin",
            "message": "Supplier GSTIN is missing.",
            "severity": "error"
        })
    else:
        if not is_valid_gstin_format(gstin):
            issues.append({
                "code": "INVALID_GSTIN_FORMAT",
                "field": "supplier_gstin",
                "message": f"GSTIN '{gstin}' is invalid (must be 15 characters matching Indian GST format).",
                "severity": "error"
            })
        elif not get_gstin_state_code(gstin):
            issues.append({
                "code": "INVALID_GSTIN_STATE_CODE",
                "field": "supplier_gstin",
                "message": f"GSTIN state prefix '{gstin[:2]}' is not a valid Indian state code.",
                "severity": "error"
            })

    # 3. CGST vs SGST parity & IGST exclusivity (error)
    cgst_paise = data.get("cgst") or 0
    sgst_paise = data.get("sgst") or 0
    igst_paise = data.get("igst") or 0
    cess_paise = data.get("cess") or 0
    general_gst_paise = data.get("gst_general") or 0

    if (cgst_paise > 0) != (sgst_paise > 0):
        issues.append({
            "code": "CGST_SGST_ASYMMETRY",
            "field": "cgst_sgst",
            "message": "CGST and SGST must both be present together for intra-state supply.",
            "severity": "error"
        })
    elif cgst_paise > 0 and sgst_paise > 0:
        # Difference greater than 100 paise (Rs. 1.00)
        if abs(cgst_paise - sgst_paise) > 100:
            issues.append({
                "code": "CGST_SGST_MISMATCH",
                "field": "cgst_sgst",
                "message": f"CGST ({cgst_paise/100:.2f}) and SGST ({sgst_paise/100:.2f}) differ.",
                "severity": "error"
            })

    if igst_paise > 0 and (cgst_paise > 0 or sgst_paise > 0):
        issues.append({
            "code": "IGST_CONFLICT",
            "field": "igst",
            "message": "IGST cannot be charged together with CGST and SGST on the same invoice.",
            "severity": "error"
        })

    # 4. Total arithmetic integrity: Subtotal + Taxes == Total within Rs. 1.00 (100 paise) (error)
    subtotal_paise = data.get("subtotal") or 0
    total_tax_paise = (cgst_paise + sgst_paise + igst_paise + cess_paise)
    if total_tax_paise == 0 and general_gst_paise > 0:
        total_tax_paise = general_gst_paise

    if subtotal_paise > 0 and total_paise > 0:
        calculated_total = subtotal_paise + total_tax_paise
        diff_paise = abs(calculated_total - total_paise)
        if diff_paise > 100:  # Rs. 1.00 tolerance for round-off
            issues.append({
                "code": "TOTAL_MISMATCH",
                "field": "total",
                "message": f"Total mismatch: Subtotal + Taxes = Rs. {calculated_total/100:.2f}, but Grand Total is Rs. {total_paise/100:.2f} (diff: Rs. {diff_paise/100:.2f}).",
                "severity": "error"
            })

    # 5. Standard GST slab check (warning)
    if subtotal_paise > 0 and total_tax_paise > 0:
        effective_rate = (total_tax_paise / subtotal_paise) * 100.0
        min_diff = min(abs(effective_rate - slab) for slab in STANDARD_GST_RATES)
        if min_diff > 0.3:
            issues.append({
                "code": "NON_STANDARD_GST_RATE",
                "field": "gst_rate",
                "message": f"Effective tax rate ({effective_rate:.1f}%) is not close to standard GST slabs (0, 0.25, 3, 5, 12, 18, 28%).",
                "severity": "warning"
            })

    # 6. Place of supply vs tax type check (warning)
    # If same state as business -> CGST + SGST expected
    # If different state -> IGST expected
    supplier_state = get_gstin_state_code(gstin)
    pos_state = data.get("place_of_supply") or supplier_state

    if business_state_code and pos_state:
        is_intra_state = (business_state_code == pos_state)
        if is_intra_state and igst_paise > 0 and cgst_paise == 0:
            issues.append({
                "code": "TAX_TYPE_POS_MISMATCH",
                "field": "place_of_supply",
                "message": f"Intra-state supply (Place of Supply: {pos_state}) should typically attract CGST + SGST, not IGST.",
                "severity": "warning"
            })
        elif not is_intra_state and (cgst_paise > 0 or sgst_paise > 0) and igst_paise == 0:
            issues.append({
                "code": "TAX_TYPE_POS_MISMATCH",
                "field": "place_of_supply",
                "message": f"Inter-state supply (Place of Supply: {pos_state} vs Business State: {business_state_code}) should typically attract IGST, not CGST + SGST.",
                "severity": "warning"
            })

    # Determine overall status
    has_error = any(issue["severity"] == "error" for issue in issues)
    has_warning = any(issue["severity"] == "warning" for issue in issues)

    if has_error:
        status = "errors"
    elif has_warning:
        status = "warnings"
    else:
        status = "ok"

    return status, issues
