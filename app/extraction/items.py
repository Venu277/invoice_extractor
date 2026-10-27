import io
import re
from typing import Any, Union
from pathlib import Path
import pdfplumber

from app.services.money import rupees_to_paise


def extract_line_items_from_pdf(
    source: Union[str, Path, bytes]
) -> tuple[list[dict[str, Any]], bool]:
    """
    Extracts structured line items from invoice PDF using pdfplumber table extraction.
    Best-effort: returns (items_list, table_found).
    Rates and amounts are in integer paise.
    """
    items: list[dict[str, Any]] = []
    table_found = False

    if isinstance(source, bytes):
        stream = io.BytesIO(source)
    else:
        stream = open(source, "rb")

    try:
        with pdfplumber.open(stream) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables() or []
                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    # Search for header row
                    header_idx = -1
                    col_map = {}
                    for idx, row in enumerate(table):
                        cleaned_row = [str(cell).strip().lower() if cell else "" for cell in row]
                        # Check if this row looks like a header
                        desc_col = None
                        hsn_col = None
                        qty_col = None
                        rate_col = None
                        taxable_col = None
                        gst_rate_col = None
                        amount_col = None

                        for c_idx, cell_text in enumerate(cleaned_row):
                            if any(k in cell_text for k in ["description", "item", "particular", "product", "goods", "services"]):
                                desc_col = c_idx
                            elif any(k in cell_text for k in ["hsn", "sac"]):
                                hsn_col = c_idx
                            elif any(k in cell_text for k in ["qty", "quantity"]):
                                qty_col = c_idx
                            elif any(k in cell_text for k in ["rate", "price", "unit price"]):
                                rate_col = c_idx
                            elif any(k in cell_text for k in ["taxable", "taxable val"]):
                                taxable_col = c_idx
                            elif any(k in cell_text for k in ["gst %", "tax %", "rate %", "gst rate"]):
                                gst_rate_col = c_idx
                            elif any(k in cell_text for k in ["total", "amount", "net amount"]):
                                amount_col = c_idx

                        if desc_col is not None or amount_col is not None:
                            header_idx = idx
                            col_map = {
                                "desc": desc_col,
                                "hsn": hsn_col,
                                "qty": qty_col,
                                "rate": rate_col,
                                "taxable": taxable_col,
                                "gst_rate": gst_rate_col,
                                "amount": amount_col
                            }
                            table_found = True
                            break

                    if header_idx != -1:
                        # Extract data rows below header
                        for row in table[header_idx + 1:]:
                            if not row:
                                continue
                            desc_val = str(row[col_map["desc"]]).strip() if col_map["desc"] is not None and col_map["desc"] < len(row) and row[col_map["desc"]] else ""
                            # Stop at summary/total rows
                            if any(k in desc_val.lower() for k in ["total", "subtotal", "taxable value", "grand total", "cgst", "sgst", "igst"]):
                                continue

                            # Skip empty description rows
                            if not desc_val or desc_val.lower() == "none":
                                continue

                            hsn_val = str(row[col_map["hsn"]]).strip() if col_map["hsn"] is not None and col_map["hsn"] < len(row) and row[col_map["hsn"]] else None
                            if hsn_val:
                                hsn_val = re.sub(r"[^\w]", "", hsn_val)

                            qty_raw = str(row[col_map["qty"]]).strip() if col_map["qty"] is not None and col_map["qty"] < len(row) and row[col_map["qty"]] else "1"
                            qty_nums = re.findall(r"\d+(?:\.\d+)?", qty_raw)
                            qty = float(qty_nums[0]) if qty_nums else 1.0

                            rate_raw = str(row[col_map["rate"]]).strip() if col_map["rate"] is not None and col_map["rate"] < len(row) and row[col_map["rate"]] else "0"
                            rate_paise = rupees_to_paise(rate_raw)

                            taxable_raw = str(row[col_map["taxable"]]).strip() if col_map["taxable"] is not None and col_map["taxable"] < len(row) and row[col_map["taxable"]] else ""
                            taxable_paise = rupees_to_paise(taxable_raw) if taxable_raw else int(rate_paise * qty)

                            gst_raw = str(row[col_map["gst_rate"]]).strip() if col_map["gst_rate"] is not None and col_map["gst_rate"] < len(row) and row[col_map["gst_rate"]] else "18"
                            gst_nums = re.findall(r"\d+(?:\.\d+)?", gst_raw)
                            gst_rate = float(gst_nums[0]) if gst_nums else 18.0

                            amount_raw = str(row[col_map["amount"]]).strip() if col_map["amount"] is not None and col_map["amount"] < len(row) and row[col_map["amount"]] else ""
                            if amount_raw:
                                amount_paise = rupees_to_paise(amount_raw)
                            else:
                                tax_calc = int(taxable_paise * (gst_rate / 100.0))
                                amount_paise = taxable_paise + tax_calc

                            items.append({
                                "description": desc_val,
                                "hsn_sac": hsn_val,
                                "quantity": qty,
                                "unit": "NOS",
                                "rate": rate_paise,
                                "taxable": taxable_paise,
                                "gst_rate": gst_rate,
                                "cgst": 0,
                                "sgst": 0,
                                "igst": 0,
                                "amount": amount_paise
                            })
    except Exception:
        # Best effort table extraction must never crash
        pass
    finally:
        if not isinstance(source, bytes) and hasattr(stream, "close"):
            stream.close()

    return items, table_found
