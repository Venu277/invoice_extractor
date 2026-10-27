from datetime import date, timedelta
from app.services.payment_service import resolve_invoice_due_date


def test_due_date_resolution_priority():
    base_date = date(2025, 4, 1)

    # 1. Extracted due date takes highest priority
    d1 = resolve_invoice_due_date(
        invoice_date=base_date,
        extracted_due_date=date(2025, 4, 10),
        extracted_terms="Net 30",
        party_terms_days=15,
        business_default_terms_days=60
    )
    assert d1 == date(2025, 4, 10)

    # 2. Extracted terms takes priority over party and business
    d2 = resolve_invoice_due_date(
        invoice_date=base_date,
        extracted_due_date=None,
        extracted_terms="Net 45 days",
        party_terms_days=15,
        business_default_terms_days=60
    )
    assert d2 == base_date + timedelta(days=45)

    # 3. Party terms takes priority over business default
    d3 = resolve_invoice_due_date(
        invoice_date=base_date,
        extracted_due_date=None,
        extracted_terms=None,
        party_terms_days=15,
        business_default_terms_days=60
    )
    assert d3 == base_date + timedelta(days=15)

    # 4. Fallback to business default
    d4 = resolve_invoice_due_date(
        invoice_date=base_date,
        extracted_due_date=None,
        extracted_terms=None,
        party_terms_days=None,
        business_default_terms_days=60
    )
    assert d4 == base_date + timedelta(days=60)


def test_payments_and_ledger_flow(client):
    # Signup owner
    client.post("/api/v1/auth/signup", json={
        "business_name": "Ledger Biz",
        "owner_name": "Ledger Owner",
        "email": "ledger@biz.com",
        "password": "Password123!"
    })
    token = client.post("/api/v1/auth/login", json={
        "email": "ledger@biz.com",
        "password": "Password123!"
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Upload inv1.pdf (total = 11,800.00 Rs = 1180000 paise)
    from pathlib import Path
    pdf_bytes = Path("invoices/inv1.pdf").read_bytes()
    client.post("/api/v1/documents/upload?sync=true", headers=headers, files=[("files", ("inv1.pdf", pdf_bytes, "application/pdf"))])

    invs = client.get("/api/v1/invoices", headers=headers).json()
    assert len(invs) >= 1
    inv = invs[0]
    inv_id = inv["id"]
    party_id = inv["party_id"]
    assert inv["payment_status"] == "unpaid"
    assert inv["amount_paid"] == 0

    # Approve invoice
    client.post(f"/api/v1/invoices/{inv_id}/approve", headers=headers)

    # 1. Partial payment: Rs. 5,000 (500000 paise)
    p1_res = client.post("/api/v1/payments", headers=headers, json={
        "invoice_id": inv_id,
        "amount": 500000,
        "method": "bank_transfer",
        "reference": "UTR123456"
    })
    assert p1_res.status_code == 201

    updated_inv1 = client.get(f"/api/v1/invoices/{inv_id}", headers=headers).json()
    assert updated_inv1["payment_status"] == "partial"
    assert updated_inv1["amount_paid"] == 500000

    # 2. Second payment for remainder: Rs. 6,800 (680000 paise)
    p2_res = client.post("/api/v1/payments", headers=headers, json={
        "invoice_id": inv_id,
        "amount": 680000,
        "method": "upi",
        "reference": "UPI98765"
    })
    assert p2_res.status_code == 201

    updated_inv2 = client.get(f"/api/v1/invoices/{inv_id}", headers=headers).json()
    assert updated_inv2["payment_status"] == "paid"
    assert updated_inv2["amount_paid"] == 1180000

    # 3. Verify party ledger
    ledger_res = client.get(f"/api/v1/payments/party/{party_id}/ledger", headers=headers)
    assert ledger_res.status_code == 200
    ledger = ledger_res.json()
    assert len(ledger["entries"]) == 3  # 1 invoice + 2 payments
    # Final balance should be 0 because invoice (credit) was fully paid (debit)
    assert ledger["current_balance"] == 0


def test_ageing_report(client):
    # Signup owner
    client.post("/api/v1/auth/signup", json={
        "business_name": "Ageing Biz",
        "owner_name": "Ageing Owner",
        "email": "ageing@biz.com",
        "password": "Password123!"
    })
    token = client.post("/api/v1/auth/login", json={
        "email": "ageing@biz.com",
        "password": "Password123!"
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Upload inv2.pdf
    from pathlib import Path
    pdf_bytes = Path("invoices/inv2.pdf").read_bytes()
    client.post("/api/v1/documents/upload?sync=true", headers=headers, files=[("files", ("inv2.pdf", pdf_bytes, "application/pdf"))])

    invs = client.get("/api/v1/invoices", headers=headers).json()
    inv_id = invs[0]["id"]
    # Reviewer confirms direction as purchase and approves
    client.put(f"/api/v1/invoices/{inv_id}", headers=headers, json={"direction": "purchase"})
    client.post(f"/api/v1/invoices/{inv_id}/approve", headers=headers)

    # Query purchase ageing (inv2 is purchase)
    ageing_res = client.get("/api/v1/reports/ageing?direction=purchase", headers=headers)
    assert ageing_res.status_code == 200
    data = ageing_res.json()
    assert data["direction"] == "purchase"
    assert data["summary"]["total_outstanding"] == 2950000
    assert len(data["party_breakdown"]) >= 1
