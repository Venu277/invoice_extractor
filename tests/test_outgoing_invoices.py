from datetime import date, timedelta
from app.models.party import Party
from app.models.business import Business
from app.models.user import User
from app.services.security import hash_password, create_access_token


def setup_generator_test(db_session):
    biz = Business(name="Generator Biz KA", gstin="29ABCDE1234F1Z5", state_code="29", invoice_prefix="GEN-")
    db_session.add(biz)
    db_session.flush()

    user = User(
        business_id=biz.id, name="Gen Owner", email="gen@biz.com",
        password_hash=hash_password("Password123!"), role="owner", is_active=True
    )
    db_session.add(user)
    db_session.flush()

    # Intra-state customer (KA)
    c_intra = Party(business_id=biz.id, name="Intra Cust", gstin="29AAAAA1111A1Z1", state_code="29", type="customer", payment_terms_days=15)
    # Inter-state customer (MH)
    c_inter = Party(business_id=biz.id, name="Inter Cust", gstin="27BBBBB2222B1Z2", state_code="27", type="customer", payment_terms_days=45)
    db_session.add_all([c_intra, c_inter])
    db_session.commit()

    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role, "business_id": biz.id})
    return token, biz.id, c_intra.id, c_inter.id


def test_invoice_generator_intra_and_inter_state(client, db_session):
    token, biz_id, c_intra_id, c_inter_id = setup_generator_test(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Generate Intra-state sales invoice (Karnataka to Karnataka -> CGST + SGST)
    inv1_res = client.post("/api/v1/generator/invoices", headers=headers, json={
        "customer_id": c_intra_id,
        "invoice_date": "2025-05-01",
        "items": [{
            "description": "Consulting Services",
            "quantity": 1.0,
            "rate_paise": 1000000,  # Rs. 10,000
            "gst_rate": 18.0
        }]
    })
    assert inv1_res.status_code == 201
    inv1 = inv1_res.json()
    assert inv1["invoice_no"].startswith("GEN-")
    assert inv1["direction"] == "sales"
    assert inv1["source"] == "generated"
    assert inv1["review_status"] == "approved"
    assert inv1["taxable"] == 1000000
    assert inv1["cgst"] == 90000  # Rs. 900
    assert inv1["sgst"] == 90000  # Rs. 900
    assert inv1["igst"] == 0
    assert inv1["total"] == 1180000
    assert inv1["due_date"] == "2025-05-16"  # +15 days terms
    assert inv1["validation_status"] == "ok"

    # 2. Generate Inter-state sales invoice (Karnataka to Maharashtra -> IGST)
    inv2_res = client.post("/api/v1/generator/invoices", headers=headers, json={
        "customer_id": c_inter_id,
        "invoice_date": "2025-05-01",
        "items": [{
            "description": "Hardware Product",
            "quantity": 2.0,
            "rate_paise": 2000000,  # Rs. 20,000 each = 40,000 taxable
            "gst_rate": 18.0
        }]
    })
    assert inv2_res.status_code == 201
    inv2 = inv2_res.json()
    assert inv2["cgst"] == 0
    assert inv2["sgst"] == 0
    assert inv2["igst"] == 720000  # Rs. 7,200 IGST
    assert inv2["total"] == 4720000
    assert inv2["due_date"] == "2025-06-15"  # +45 days terms
    assert inv2["validation_status"] == "ok"

    # 3. Test PDF generation endpoint
    pdf_res = client.get(f"/api/v1/generator/invoices/{inv1['id']}/pdf", headers=headers)
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF")


def test_sharing_and_revocation(client, db_session):
    token, biz_id, c_intra_id, _ = setup_generator_test(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # Generate an invoice to share
    inv = client.post("/api/v1/generator/invoices", headers=headers, json={
        "customer_id": c_intra_id,
        "invoice_date": "2025-05-01",
        "items": [{"description": "Shared Item", "quantity": 1.0, "rate_paise": 500000, "gst_rate": 18.0}]
    }).json()

    # Create share link
    share_res = client.post(f"/api/v1/shares?kind=invoice&ref={inv['id']}", headers=headers)
    assert share_res.status_code == 201
    share = share_res.json()
    assert "/s/" in share["share_url"]
    assert "wa.me" in share["whatsapp_url"]
    share_token = share["token"]

    # Revoke share link
    rev_res = client.delete(f"/api/v1/shares/{share_token}", headers=headers)
    assert rev_res.status_code == 204


def test_recurring_invoices(client, db_session):
    token, biz_id, c_intra_id, _ = setup_generator_test(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # Create monthly recurring template starting today
    t_res = client.post("/api/v1/recurring", headers=headers, json={
        "party_id": c_intra_id,
        "frequency": "monthly",
        "start_date": str(date.today()),
        "items": [{
            "description": "Monthly Retainer",
            "quantity": 1.0,
            "rate_paise": 2500000,
            "gst_rate": 18.0
        }]
    })
    assert t_res.status_code == 201

    # Trigger process
    proc_res = client.post("/api/v1/recurring/process", headers=headers)
    assert proc_res.status_code == 200
    invoices = proc_res.json()
    assert len(invoices) >= 1
    assert any("Monthly Retainer" in str(inv) for inv in invoices)
