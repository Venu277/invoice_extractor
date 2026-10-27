import os
import uuid
import zipfile
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models.document import ImportBatch, Document
from app.models.invoice import Invoice, InvoiceItem
from app.models.business import Business
from app.extraction.pipeline import process_invoice_extraction
from app.extraction.reader import is_valid_pdf_bytes, PDFReadException
from app.services.party_service import get_or_create_party_from_invoice

logger = logging.getLogger(__name__)

# In-process worker thread pool for extraction jobs
executor = ThreadPoolExecutor(max_workers=3)


def handle_file_upload(
    db: Session,
    business_id: int,
    user_id: int,
    files_data: list[tuple[str, bytes]],
    sync: bool = False
) -> ImportBatch:
    """
    Accepts raw uploaded files (PDFs and ZIP archives).
    Unpacks ZIPs, validates magic bytes, and dispatches batch processing.
    """
    valid_pdfs: list[tuple[str, bytes]] = []

    for filename, raw_bytes in files_data:
        # Check if ZIP archive
        if filename.lower().endswith(".zip") or raw_bytes.startswith(b"PK\x03\x04"):
            try:
                import io
                with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                    for name in z.namelist():
                        if name.lower().endswith(".pdf") and not name.startswith("__MACOSX"):
                            pdf_bytes = z.read(name)
                            if len(pdf_bytes) <= 10 * 1024 * 1024 and is_valid_pdf_bytes(pdf_bytes):
                                valid_pdfs.append((os.path.basename(name), pdf_bytes))
            except Exception as e:
                logger.error(f"Error extracting ZIP archive {filename}: {e}")
        else:
            # Single PDF file
            if len(raw_bytes) <= 10 * 1024 * 1024 and is_valid_pdf_bytes(raw_bytes):
                valid_pdfs.append((filename, raw_bytes))

    # Create ImportBatch record
    batch = ImportBatch(
        business_id=business_id,
        created_by=user_id,
        total=len(valid_pdfs),
        done=0,
        failed=0,
        status="processing" if valid_pdfs else "completed"
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    if valid_pdfs:
        if sync:
            process_batch_files(db, batch.id, business_id, user_id, valid_pdfs)
        else:
            executor.submit(_process_batch_background, batch.id, business_id, user_id, valid_pdfs)

    return batch


def _process_batch_background(
    batch_id: int,
    business_id: int,
    user_id: int,
    files: list[tuple[str, bytes]]
):
    """Background worker entry using dedicated session."""
    db = SessionLocal()
    try:
        process_batch_files(db, batch_id, business_id, user_id, files)
    finally:
        db.close()


def process_batch_files(
    db: Session,
    batch_id: int,
    business_id: int,
    user_id: int,
    files: list[tuple[str, bytes]]
):
    """Core batch file processor."""
    try:
        biz = db.query(Business).filter(Business.id == business_id).first()
        business_gstin = biz.gstin if biz else None
        business_state = biz.state_code if biz else None

        for filename, raw_bytes in files:
            # Save file under random uuid in uploads directory
            safe_filename = f"{uuid.uuid4().hex}.pdf"
            stored_path = settings.upload_path / safe_filename
            with open(stored_path, "wb") as f:
                f.write(raw_bytes)

            try:
                # Run extraction pipeline
                result = process_invoice_extraction(
                    source=raw_bytes,
                    filename=filename,
                    business_gstin=business_gstin,
                    business_state_code=business_state
                )

                fields = result["fields"]
                file_sha256 = result["sha256"]

                # 1. Create Document record
                doc = Document(
                    business_id=business_id,
                    batch_id=batch_id,
                    uploaded_by=user_id,
                    original_name=filename,
                    stored_path=str(stored_path),
                    sha256=file_sha256,
                    page_count=result["page_count"],
                    extraction_method=result["extraction_method"],
                    raw_text=result["raw_text"],
                    status="extracted"
                )
                db.add(doc)
                db.flush()

                # 2. Duplicate Detection
                # Check 2a: Existing identical file hash
                existing_doc = db.query(Document).filter(
                    Document.business_id == business_id,
                    Document.sha256 == file_sha256,
                    Document.id != doc.id
                ).first()

                if existing_doc:
                    result["validation_issues"].append({
                        "code": "DUPLICATE_FILE_HASH",
                        "field": "file",
                        "message": f"Identical file already uploaded in document #{existing_doc.id}.",
                        "severity": "error"
                    })
                    result["validation_status"] = "errors"

                # 3. Party Matching / Creation
                direction = fields.get("direction") or "purchase"
                party_name = fields.get("vendor") or "Unknown Vendor"
                party_gstin = fields.get("supplier_gstin")

                party = get_or_create_party_from_invoice(
                    db=db,
                    business_id=business_id,
                    name=party_name,
                    gstin=party_gstin,
                    state_code=fields.get("place_of_supply"),
                    direction=direction
                )

                # Check 2b: Duplicate (Party + Invoice No)
                inv_no = fields.get("invoice_no")
                if party and inv_no:
                    existing_inv = db.query(Invoice).filter(
                        Invoice.business_id == business_id,
                        Invoice.party_id == party.id,
                        Invoice.invoice_no == inv_no,
                        Invoice.deleted_at.is_(None)
                    ).first()
                    if existing_inv:
                        result["validation_issues"].append({
                            "code": "DUPLICATE_INVOICE_NO",
                            "field": "invoice_no",
                            "message": f"Invoice '{inv_no}' for '{party.name}' already exists in your records (Invoice #{existing_inv.id}).",
                            "severity": "error"
                        })
                        result["validation_status"] = "errors"

                # 4. Create Invoice in pending_review
                inv = Invoice(
                    business_id=business_id,
                    party_id=party.id if party else None,
                    document_id=doc.id,
                    direction=direction,
                    source="extracted",
                    invoice_no=inv_no or f"PENDING-{uuid.uuid4().hex[:6].upper()}",
                    invoice_date=fields.get("date"),
                    due_date=fields.get("due_date"),
                    supplier_gstin=party_gstin,
                    buyer_gstin=fields.get("buyer_gstin"),
                    place_of_supply_state=fields.get("place_of_supply"),
                    taxable=fields.get("subtotal") or 0,
                    cgst=fields.get("cgst") or 0,
                    sgst=fields.get("sgst") or 0,
                    igst=fields.get("igst") or 0,
                    cess=fields.get("cess") or 0,
                    total=fields.get("total") or 0,
                    amount_paid=0,
                    payment_status="unpaid",
                    review_status="pending_review",
                    validation_status=result["validation_status"],
                    validation_issues=result["validation_issues"],
                    field_confidence=fields.get("confidence") or {},
                    created_by=user_id
                )
                db.add(inv)
                db.flush()

                # 5. Add line items if present
                for item_dict in result["items"]:
                    item = InvoiceItem(
                        invoice_id=inv.id,
                        description=item_dict["description"],
                        hsn_sac=item_dict.get("hsn_sac"),
                        quantity=item_dict.get("quantity", 1.0),
                        unit=item_dict.get("unit", "NOS"),
                        rate=item_dict.get("rate", 0),
                        taxable=item_dict.get("taxable", 0),
                        gst_rate=item_dict.get("gst_rate", 18.0),
                        cgst=item_dict.get("cgst", 0),
                        sgst=item_dict.get("sgst", 0),
                        igst=item_dict.get("igst", 0),
                        amount=item_dict.get("amount", 0)
                    )
                    db.add(item)

                db.commit()

                # Update batch progress
                batch = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
                if batch:
                    batch.done += 1
                    db.commit()

            except Exception as e:
                logger.error(f"Error processing file {filename} in batch {batch_id}: {e}", exc_info=True)
                db.rollback()
                doc = Document(
                    business_id=business_id,
                    batch_id=batch_id,
                    uploaded_by=user_id,
                    original_name=filename,
                    stored_path=str(stored_path),
                    sha256="",
                    status="failed",
                    error=str(e)
                )
                db.add(doc)
                batch = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
                if batch:
                    batch.failed += 1
                db.commit()

        # Final batch status
        batch = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
        if batch:
            batch.status = "completed"
            db.commit()

    except Exception as e:
        logger.error(f"Fatal error in batch {batch_id}: {e}", exc_info=True)
