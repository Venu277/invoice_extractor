import io
import time
from pathlib import Path
import pytest
from app.models.invoice import Invoice
from app.models.document import Document, ImportBatch


def test_upload_and_review_flow(client):
    # 1. Signup business owner
    s = client.post("/api/v1/auth/signup", json={
        "business_name": "Review Test Biz",
        "owner_name": "Reviewer",
        "email": "reviewer@biz.com",
        "password": "Password123!",
        "gstin": "29ABCDE1234F1Z5"
    })
    token = client.post("/api/v1/auth/login", json={
        "email": "reviewer@biz.com",
        "password": "Password123!"
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload inv1.pdf
    pdf_bytes = Path("invoices/inv1.pdf").read_bytes()
    upload_res = client.post(
        "/api/v1/documents/upload?sync=true",
        headers=headers,
        files=[("files", ("inv1.pdf", pdf_bytes, "application/pdf"))]
    )
    assert upload_res.status_code == 202
    batch_data = upload_res.json()
    batch_id = batch_data["id"]
    assert batch_id > 0

    # 3. Poll batch progress
    progress_res = client.get(f"/api/v1/documents/batches/{batch_id}", headers=headers)
    assert progress_res.status_code == 200
    assert progress_res.json()["done"] >= 1

    # 4. Invoices list should contain newly extracted invoice
    inv_list_res = client.get("/api/v1/invoices", headers=headers)
    assert inv_list_res.status_code == 200
    invoices = inv_list_res.json()
    assert len(invoices) >= 1
    inv = invoices[0]
    assert inv["invoice_no"] == "INV-1001"
    assert inv["review_status"] == "pending_review"
    inv_id = inv["id"]

    # 5. Verify Party was auto-created
    parties_res = client.get("/api/v1/parties", headers=headers)
    assert parties_res.status_code == 200
    parties = parties_res.json()
    assert any("Sharma Traders" in p["name"] for p in parties)

    # 6. Edit invoice & re-run validation
    edit_res = client.put(
        f"/api/v1/invoices/{inv_id}",
        headers=headers,
        json={
            "invoice_no": "INV-1001-EDITED",
            "total": 1180000
        }
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["invoice_no"] == "INV-1001-EDITED"

    # 7. Approve invoice
    approve_res = client.post(f"/api/v1/invoices/{inv_id}/approve", headers=headers)
    assert approve_res.status_code == 200
    assert approve_res.json()["review_status"] == "approved"
    assert approve_res.json()["approved_at"] is not None

    # 8. Soft-delete invoice
    del_res = client.delete(f"/api/v1/invoices/{inv_id}", headers=headers)
    assert del_res.status_code == 204

    # Deleted invoice must not show in list
    active_invs = client.get("/api/v1/invoices", headers=headers).json()
    assert all(i["id"] != inv_id for i in active_invs)


def test_duplicate_file_and_invoice_detection(client):
    token = client.post("/api/v1/auth/signup", json={
        "business_name": "Dup Test Biz",
        "owner_name": "Dup Tester",
        "email": "dup@tester.com",
        "password": "Password123!"
    }).json()["email"]
    auth_header = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': 'dup@tester.com', 'password': 'Password123!'}).json()['access_token']}"}

    pdf_bytes = Path("invoices/inv2.pdf").read_bytes()

    # Upload first time
    client.post("/api/v1/documents/upload?sync=true", headers=auth_header, files=[("files", ("inv2.pdf", pdf_bytes, "application/pdf"))])

    # Upload second time (duplicate file hash)
    client.post("/api/v1/documents/upload?sync=true", headers=auth_header, files=[("files", ("inv2_copy.pdf", pdf_bytes, "application/pdf"))])

    invoices = client.get("/api/v1/invoices", headers=auth_header).json()
    assert len(invoices) >= 2
    # The duplicate invoice should be flagged with DUPLICATE_FILE_HASH or DUPLICATE_INVOICE_NO error
    dup_inv = invoices[0] if "DUPLICATE" in str(invoices[0]["validation_issues"]) else invoices[1]
    issue_codes = [i["code"] for i in dup_inv["validation_issues"]]
    assert any("DUPLICATE" in c for c in issue_codes)
    assert dup_inv["validation_status"] == "errors"
