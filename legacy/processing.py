"""Runs one uploaded PDF through the extraction pipeline (read -> extract -> validate)."""
import os
import tempfile

from extractor import read_pdf_text, extract_fields, validate, COLUMNS
from database import month_key


def process_pdf(name, data):
    """Returns (row_dict, readable). 'readable' is False if nothing could be extracted."""
    row = {c: None for c in COLUMNS}
    row["file"] = name
    readable = False

    # the PDF readers need a file path, so write the upload to a temporary file first
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        tmp.write(data)
        tmp.close()                                   # must close before reading (Windows)

        text = read_pdf_text(tmp.name)
        if not text.strip():
            row["status"] = "No text found (scanned PDF? OCR needed)"
        else:
            row = extract_fields(text)
            row["file"] = name
            row["status"] = validate(row)
            readable = True

            # dates we could not convert cannot be grouped by month, so flag them
            if row["date"] and month_key(row["date"]) is None:
                note = "Date format not recognised"
                row["status"] = note if row["status"] == "OK" else row["status"] + "; " + note
    except Exception as e:
        row = {c: None for c in COLUMNS}
        row["file"] = name
        row["status"] = f"Error: {e}"
        readable = False
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)

    return row, readable