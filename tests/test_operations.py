from app.models.business import Business
from app.models.user import User
from app.services.security import hash_password, create_access_token
from app.services.share_service import create_share_link


def setup_operations_test(db_session):
    biz = Business(name="Ops Biz", gstin="29ABCDE1234F1Z5", state_code="29")
    db_session.add(biz)
    db_session.flush()

    user = User(
        business_id=biz.id, name="Ops Owner", email="ops@biz.com",
        password_hash=hash_password("Password123!"), role="owner", is_active=True
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role, "business_id": biz.id})
    return token, biz.id


def test_backup_and_restore_flow(client, db_session):
    token, biz_id = setup_operations_test(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Trigger manual backup
    res = client.post("/api/v1/backups", headers=headers)
    assert res.status_code == 201
    b_id = res.json()["id"]
    assert b_id > 0

    # 2. List backups
    list_res = client.get("/api/v1/backups", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Restore backup with confirmation
    restore_res = client.post(f"/api/v1/backups/{b_id}/restore?confirm=true", headers=headers)
    assert restore_res.status_code == 200
    assert "restored" in restore_res.json()["message"].lower()


def test_public_share_and_pdf_download(client, db_session):
    token, biz_id = setup_operations_test(db_session)

    # Create share link for a monthly report
    link = create_share_link(db_session, biz_id, kind="report", ref="2025-04")

    # Access public share page without authentication
    pub_res = client.get(f"/s/{link.token}")
    assert pub_res.status_code == 200
    assert "Shared Document" in pub_res.text

    # Access public PDF stream
    pdf_res = client.get(f"/s/{link.token}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF")


def test_web_routes_rendering(client):
    # 1. Login page
    login_res = client.get("/login")
    assert login_res.status_code == 200
    assert "InvoiceIQ" in login_res.text

    # 2. Root redirects
    root_res = client.get("/", follow_redirects=False)
    assert root_res.status_code == 307 or root_res.status_code == 303 or root_res.status_code == 302


def test_approved_invoice_reflects_in_reports_and_exports(client, db_session):
    from datetime import date
    from app.models.invoice import Invoice
    from app.models.party import Party

    token, biz_id = setup_operations_test(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a party and pending invoice with unknown direction
    party = Party(business_id=biz_id, name="Test Supplier", gstin="27AABCU9603R1ZM", type="vendor")
    db_session.add(party)
    db_session.flush()

    inv = Invoice(
        business_id=biz_id,
        party_id=party.id,
        direction="unknown",
        source="extracted",
        invoice_no="TEST-EXP-01",
        invoice_date=date(2025, 4, 15),
        supplier_gstin="27AABCU9603R1ZM",
        taxable=1000000,  # Rs. 10,000.00
        igst=180000,      # Rs. 1,800.00
        total=1180000,    # Rs. 11,800.00
        payment_status="unpaid",
        review_status="pending_review",
        validation_status="ok"
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)

    # 2. Approve invoice via API
    approve_res = client.post(f"/api/v1/invoices/{inv.id}/approve", headers=headers)
    assert approve_res.status_code == 200
    approved_data = approve_res.json()
    assert approved_data["review_status"] == "approved"
    assert approved_data["direction"] == "purchase"  # Auto-resolved from unknown to purchase!

    # 3. Verify P&L immediately reflects the purchase expenses
    pnl_res = client.get("/api/v1/reports/profit-and-loss", headers=headers)
    assert pnl_res.status_code == 200
    pnl_data = pnl_res.json()
    assert pnl_data["expenses"]["purchase_count"] >= 1
    assert pnl_data["expenses"]["taxable"] >= 1000000

    # 4. Verify GSTR-3B immediately reflects the ITC
    gstr_res = client.get("/api/v1/gst/gstr3b", headers=headers)
    assert gstr_res.status_code == 200
    gstr_data = gstr_res.json()
    assert gstr_data["itc_eligible"]["total_itc"] >= 180000

    # 5. Verify Exports & Tally page renders the approved voucher
    client.cookies.set("access_token", token)
    exp_page_res = client.get("/exports")
    assert exp_page_res.status_code == 200
    assert "TEST-EXP-01" in exp_page_res.text
    assert "Ready for Export" in exp_page_res.text
