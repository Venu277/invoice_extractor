from datetime import date
from decimal import Decimal
from app.models.invoice import Invoice, InvoiceItem
from app.models.party import Party
from app.models.business import Business
from app.models.user import User
from app.services.security import hash_password, create_access_token


def setup_golden_dataset(db_session):
    """
    Creates the Section 11 Golden Dataset:
    Business in Karnataka (state 29).
    S1: Sales, Karnataka, Taxable 10,000, CGST 900, SGST 900, Total 11,800, HSN 4820 (qty 10)
    S2: Sales, Maharashtra, Taxable 40,000, IGST 7,200, Total 47,200, HSN 8471 (qty 2)
    P1: Purchase, Karnataka, Taxable 25,000, CGST 2,250, SGST 2,250, Total 29,500
    P2: Purchase, Delhi, Taxable 5,000, IGST 900, Total 5,900
    """
    biz = Business(
        name="Golden Karnataka Biz",
        gstin="29ABCDE1234F1Z5",
        state_code="29"
    )
    db_session.add(biz)
    db_session.flush()

    user = User(
        business_id=biz.id,
        name="Golden Owner",
        email="golden@biz.com",
        password_hash=hash_password("Password123!"),
        role="owner",
        is_active=True
    )
    db_session.add(user)
    db_session.flush()

    # Parties
    party_c1 = Party(business_id=biz.id, name="Customer KA", gstin="29AAAAA1111A1Z1", state_code="29", type="customer")
    party_c2 = Party(business_id=biz.id, name="Customer MH", gstin="27BBBBB2222B1Z2", state_code="27", type="customer")
    party_v1 = Party(business_id=biz.id, name="Vendor KA", gstin="29CCCCC3333C1Z3", state_code="29", type="vendor")
    party_v2 = Party(business_id=biz.id, name="Vendor DL", gstin="07DDDDD4444D1Z4", state_code="07", type="vendor")
    db_session.add_all([party_c1, party_c2, party_v1, party_v2])
    db_session.flush()

    # S1: Sales, KA, 10k + 900 CGST + 900 SGST = 11,800
    s1 = Invoice(
        business_id=biz.id, party_id=party_c1.id, direction="sales", source="generated",
        invoice_no="S1", invoice_date=date(2025, 4, 10), buyer_gstin=party_c1.gstin, place_of_supply_state="29",
        taxable=1000000, cgst=90000, sgst=90000, igst=0, cess=0, total=1180000,
        review_status="approved", payment_status="unpaid"
    )
    db_session.add(s1)
    db_session.flush()
    db_session.add(InvoiceItem(
        invoice_id=s1.id, description="Item S1", hsn_sac="4820", quantity=10.0,
        rate=100000, taxable=1000000, gst_rate=18.0, cgst=90000, sgst=90000, igst=0, amount=1180000
    ))

    # S2: Sales, MH, 40k + 7,200 IGST = 47,200
    s2 = Invoice(
        business_id=biz.id, party_id=party_c2.id, direction="sales", source="generated",
        invoice_no="S2", invoice_date=date(2025, 4, 15), buyer_gstin=party_c2.gstin, place_of_supply_state="27",
        taxable=4000000, cgst=0, sgst=0, igst=720000, cess=0, total=4720000,
        review_status="approved", payment_status="unpaid"
    )
    db_session.add(s2)
    db_session.flush()
    db_session.add(InvoiceItem(
        invoice_id=s2.id, description="Item S2", hsn_sac="8471", quantity=2.0,
        rate=2000000, taxable=4000000, gst_rate=18.0, cgst=0, sgst=0, igst=720000, amount=4720000
    ))

    # P1: Purchase, KA, 25k + 2,250 CGST + 2,250 SGST = 29,500
    p1 = Invoice(
        business_id=biz.id, party_id=party_v1.id, direction="purchase", source="extracted",
        invoice_no="P1", invoice_date=date(2025, 4, 20), supplier_gstin=party_v1.gstin, place_of_supply_state="29",
        taxable=2500000, cgst=225000, sgst=225000, igst=0, cess=0, total=2950000,
        review_status="approved", payment_status="unpaid"
    )
    db_session.add(p1)

    # P2: Purchase, DL, 5k + 900 IGST = 5,900
    p2 = Invoice(
        business_id=biz.id, party_id=party_v2.id, direction="purchase", source="extracted",
        invoice_no="P2", invoice_date=date(2025, 4, 25), supplier_gstin=party_v2.gstin, place_of_supply_state="07",
        taxable=500000, cgst=0, sgst=0, igst=90000, cess=0, total=590000,
        review_status="approved", payment_status="unpaid"
    )
    db_session.add(p2)
    db_session.commit()

    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "business_id": biz.id
    })
    return token, biz.id


def test_golden_dataset_gst_and_pnl(client, db_session):
    token, biz_id = setup_golden_dataset(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Verify Profit and Loss
    # Expected: income 50,000 (5,000,000 paise), expenses 30,000 (3,000,000 paise), profit 20,000 (2,000,000 paise)
    pnl = client.get("/api/v1/reports/profit-and-loss?fy=2025", headers=headers).json()
    assert pnl["income"]["taxable"] == 5000000
    assert pnl["expenses"]["taxable"] == 3000000
    assert pnl["net_profit"] == 2000000

    # 2. Verify GSTR-3B Summary and Tax Set-off
    # Output: CGST 900 (90,000 paise), SGST 900 (90,000 paise), IGST 7,200 (720,000 paise)
    # ITC: CGST 2,250 (225,000 paise), SGST 2,250 (225,000 paise), IGST 900 (90,000 paise)
    # Net cash payable after set-off: IGST 3,600 (360,000 paise) and nothing else!
    gstr3b = client.get("/api/v1/gst/gstr3b?fy=2025", headers=headers).json()
    outward = gstr3b["outward_supplies"]
    assert outward["cgst"] == 90000
    assert outward["sgst"] == 90000
    assert outward["igst"] == 720000

    itc = gstr3b["itc_eligible"]
    assert itc["cgst"] == 225000
    assert itc["sgst"] == 225000
    assert itc["igst"] == 90000

    set_off = gstr3b["set_off_summary"]
    assert set_off["cash_payable_cgst"] == 0
    assert set_off["cash_payable_sgst"] == 0
    assert set_off["cash_payable_igst"] == 360000  # Rs. 3,600
    assert set_off["total_cash_payable"] == 360000

    # 3. Verify HSN Summary
    # S1: HSN 4820 (qty 10, taxable 10,000)
    # S2: HSN 8471 (qty 2, taxable 40,000)
    hsn_res = client.get("/api/v1/gst/hsn?fy=2025", headers=headers).json()
    rows = hsn_res["rows"]
    hsn_map = {r["hsn_sac"]: r for r in rows}
    assert "4820" in hsn_map
    assert hsn_map["4820"]["quantity"] == 10.0
    assert hsn_map["4820"]["taxable"] == 1000000

    assert "8471" in hsn_map
    assert hsn_map["8471"]["quantity"] == 2.0
    assert hsn_map["8471"]["taxable"] == 4000000


def test_exports(client, db_session):
    token, biz_id = setup_golden_dataset(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. CSV Export
    csv_res = client.get("/api/v1/exports/csv", headers=headers)
    assert csv_res.status_code == 200
    assert "Invoice No,Date" in csv_res.text
    assert "S1" in csv_res.text
    assert "S2" in csv_res.text

    # 2. Excel Export
    excel_res = client.get("/api/v1/exports/excel", headers=headers)
    assert excel_res.status_code == 200
    assert len(excel_res.content) > 1000

    # 3. Tally XML Export
    tally_res = client.get("/api/v1/exports/tally", headers=headers)
    assert tally_res.status_code == 200
    xml_text = tally_res.text
    assert "<ENVELOPE>" in xml_text
    assert "<VOUCHER" in xml_text
    assert "Golden Karnataka Biz" not in xml_text or "Customer KA" in xml_text

    # 4. Accountant Package ZIP
    zip_res = client.get("/api/v1/exports/accountant-package?month=2025-04", headers=headers)
    assert zip_res.status_code == 200
    assert zip_res.content.startswith(b"PK\x03\x04")
