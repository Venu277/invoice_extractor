import hashlib
from pathlib import Path
from typing import Any, Union

from app.extraction.reader import read_pdf_content
from app.extraction.fields import extract_all_fields
from app.extraction.items import extract_line_items_from_pdf
from app.extraction.validate import validate_invoice_data


def process_invoice_extraction(
    source: Union[str, Path, bytes],
    filename: str,
    business_gstin: str | None = None,
    business_state_code: str | None = None
) -> dict[str, Any]:
    """
    Executes the end-to-end extraction pipeline:
    1. Read PDF text & pages
    2. Extract header & tax fields
    3. Extract line items table
    4. Classify transaction direction
    5. Validate statutory GST rules & totals
    """
    if isinstance(source, bytes):
        raw_bytes = source
    else:
        with open(source, "rb") as f:
            raw_bytes = f.read()

    file_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    # 1. Read PDF content
    text, method, page_count, _ = read_pdf_content(raw_bytes)

    # 2. Extract fields
    fields = extract_all_fields(text, business_gstin=business_gstin)

    # 3. Extract line items
    items, table_found = extract_line_items_from_pdf(raw_bytes)

    # 4. Validate GST rules & totals
    val_status, issues = validate_invoice_data(fields, business_state_code=business_state_code)

    if not table_found and not items:
        # Best effort note - never blocks saving
        issues.append({
            "code": "NO_LINE_ITEMS_TABLE",
            "field": "items",
            "message": "Structured line items table not detected; header totals were extracted.",
            "severity": "warning"
        })
        if val_status == "ok":
            val_status = "warnings"

    return {
        "filename": filename,
        "sha256": file_sha256,
        "page_count": page_count,
        "extraction_method": method,
        "raw_text": text,
        "fields": fields,
        "items": items,
        "validation_status": val_status,
        "validation_issues": issues
    }
