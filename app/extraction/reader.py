import io
import os
import shutil
import logging
from pathlib import Path
from typing import Union
import pdfplumber
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import settings

logger = logging.getLogger(__name__)


class PDFReadException(Exception):
    pass


class PDFEncryptedError(PDFReadException):
    pass


class PDFCorruptError(PDFReadException):
    pass


def is_valid_pdf_bytes(data: bytes) -> bool:
    """Verifies PDF magic bytes."""
    return data.startswith(b"%PDF")


def read_pdf_content(
    source: Union[str, Path, bytes]
) -> tuple[str, str, int, list[str]]:
    """
    Reads text from a PDF source using 3-tier fallback:
    1. pdfplumber
    2. pypdf
    3. OCR page-by-page (pytesseract + pdf2image) if available and text is sparse.

    Returns:
        (full_text, extraction_method, page_count, pages_text)
    """
    if isinstance(source, bytes):
        if not is_valid_pdf_bytes(source):
            raise PDFCorruptError("Invalid file header: Not a valid PDF file.")
        stream = io.BytesIO(source)
    else:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found at {path}")
        with open(path, "rb") as f:
            header = f.read(5)
            if not is_valid_pdf_bytes(header):
                raise PDFCorruptError("Invalid file header: Not a valid PDF file.")
        stream = open(path, "rb")

    try:
        # Check encryption and corruption with pypdf first
        stream.seek(0)
        try:
            pypdf_reader = PdfReader(stream)
            if pypdf_reader.is_encrypted:
                # Try empty password
                try:
                    pypdf_reader.decrypt("")
                except Exception:
                    raise PDFEncryptedError("PDF is password protected and encrypted.")
            page_count = len(pypdf_reader.pages)
        except PDFEncryptedError:
            raise
        except PdfReadError as e:
            raise PDFCorruptError(f"Corrupt or malformed PDF: {e}")
        except Exception as e:
            raise PDFCorruptError(f"Unable to parse PDF structure: {e}")

        # Tier 1: Try pdfplumber
        stream.seek(0)
        plumber_pages_text = []
        try:
            with pdfplumber.open(stream) as pdf:
                for page in pdf.pages:
                    txt = page.extract_text() or ""
                    plumber_pages_text.append(txt)
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")
            plumber_pages_text = []

        combined_text = "\n".join(plumber_pages_text).strip()
        if combined_text:
            return "\n".join(plumber_pages_text), "text", page_count, plumber_pages_text

        # Tier 2: Try pypdf fallback
        stream.seek(0)
        pypdf_pages_text = []
        try:
            pypdf_reader = PdfReader(stream)
            for page in pypdf_reader.pages:
                txt = page.extract_text() or ""
                pypdf_pages_text.append(txt)
        except Exception as e:
            logger.warning(f"pypdf extraction failed: {e}")
            pypdf_pages_text = []

        combined_text = "\n".join(pypdf_pages_text).strip()
        if combined_text:
            return "\n".join(pypdf_pages_text), "text", page_count, pypdf_pages_text

        # Tier 3: OCR page by page (for scanned invoices)
        if settings.OCR_ENABLED:
            ocr_text, ocr_success = _extract_with_ocr(source, page_count)
            if ocr_success and ocr_text.strip():
                return ocr_text, "ocr", page_count, [ocr_text]

        # No text found
        return "", "none", page_count, []

    finally:
        if not isinstance(source, bytes) and hasattr(stream, "close"):
            stream.close()


def _extract_with_ocr(source: Union[str, Path, bytes], expected_pages: int) -> tuple[str, bool]:
    """Graceful OCR fallback using pytesseract & pdf2image."""
    try:
        import pytesseract
        from pdf2image import convert_from_bytes, convert_from_path

        if settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        elif shutil.which("tesseract"):
            pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract")
        else:
            # Tesseract binary not found; degrade gracefully
            logger.info("Tesseract binary not found. Skipping OCR.")
            return "", False

        poppler_path = settings.POPPLER_PATH if settings.POPPLER_PATH else None

        if isinstance(source, bytes):
            images = convert_from_bytes(source, poppler_path=poppler_path)
        else:
            images = convert_from_path(str(source), poppler_path=poppler_path)

        extracted_pages = []
        for img in images:
            txt = pytesseract.image_to_string(img)
            extracted_pages.append(txt)

        return "\n".join(extracted_pages), True
    except Exception as e:
        logger.warning(f"OCR degradation: {e}")
        return "", False
