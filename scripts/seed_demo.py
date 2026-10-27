import os
import sys
from pathlib import Path
from datetime import date, datetime

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, Base, engine
from app.models.business import Business
from app.models.user import User
from app.models.party import Party
from app.models.invoice import Invoice, InvoiceItem
from app.models.document import Document
from app.services.security import hash_password, generate_recovery_code


def seed():
    print("Seeding InvoiceIQ Demo Dataset...")
    db = SessionLocal()
    try:
        # Check if demo business already exists
        biz = db.query(Business).filter(Business.gstin == "29ABCDE1234F1Z5").first()
        if not biz:
            biz = Business(
                name="InvoiceIQ Demo Enterprises",
                gstin="29ABCDE1234F1Z5",
                state_code="29",
                address="108 Industrial Area, Phase 2, Bangalore, Karnataka 560001",
                phone="+91 98765 43210",
                email="contact@invoiceiq-demo.com",
                bank_name="HDFC Bank",
                account_no="50100234567890",
                ifsc="HDFC0001234",
                upi_id="demo@hdfcbank",
                invoice_prefix="IIQ-",
                fy_start_month=4,
                default_payment_terms_days=30
            )
            db.add(biz)
            db.flush()

        # Users: Owner, Accountant, Staff
        roles = [
            ("Demo Owner", "owner@demo.com", "owner"),
            ("Demo Accountant", "accountant@demo.com", "accountant"),
            ("Demo Staff", "staff@demo.com", "staff")
        ]

        for name, email, role in roles:
            u = db.query(User).filter(User.email == email).first()
            if not u:
                rec_code = generate_recovery_code()
                u = User(
                    business_id=biz.id,
                    name=name,
                    email=email,
                    password_hash=hash_password("DemoPassword123!"),
                    role=role,
                    recovery_hash=hash_password(rec_code),
                    is_active=True
                )
                db.add(u)
                print(f"Created {role.capitalize()}: {email} / DemoPassword123! (Recovery: {rec_code})")

        db.flush()

        # Parties (Golden Dataset & Test Parties)
        parties_data = [
            ("Customer Karnataka Ltd", "29AAAAA1111A1Z1", "29", "customer"),
            ("Customer Maharashtra Corp", "27BBBBB2222B1Z2", "27", "customer"),
            ("Sharma Traders Bangalore", "29CCCCC3333C1Z3", "29", "vendor"),
            ("Delhi Hardware Supplies", "07DDDDD4444D1Z4", "07", "vendor")
        ]
        party_map = {}
        for p_name, gstin, st, p_type in parties_data:
            p = db.query(Party).filter(Party.business_id == biz.id, Party.name == p_name).first()
            if not p:
                p = Party(
                    business_id=biz.id,
                    name=p_name,
                    gstin=gstin,
                    state_code=st,
                    type=p_type,
                    payment_terms_days=30,
                    credit_limit_paise=10000000  # Rs. 1,00,000
                )
                db.add(p)
                db.flush()
            party_map[p_name] = p

        # Golden Dataset Invoices
        # S1: Sales, Karnataka, Taxable 10,000, CGST 900, SGST 900, Total 11,800
        if not db.query(Invoice).filter(Invoice.business_id == biz.id, Invoice.invoice_no == "IIQ-S1").first():
            s1 = Invoice(
                business_id=biz.id, party_id=party_map["Customer Karnataka Ltd"].id, direction="sales", source="generated",
                invoice_no="IIQ-S1", invoice_date=date(2025, 4, 10), due_date=date(2025, 5, 10),
                buyer_gstin="29AAAAA1111A1Z1", place_of_supply_state="29",
                taxable=1000000, cgst=90000, sgst=90000, igst=0, cess=0, total=1180000,
                review_status="approved", payment_status="unpaid", validation_status="ok"
            )
            db.add(s1)
            db.flush()
            db.add(InvoiceItem(
                invoice_id=s1.id, description="Stationery & Office Paper", hsn_sac="4820", quantity=10.0,
                unit="BOX", rate=100000, taxable=1000000, gst_rate=18.0, cgst=90000, sgst=90000, igst=0, amount=1180000
            ))

        # S2: Sales, Maharashtra, Taxable 40,000, IGST 7,200, Total 47,200
        if not db.query(Invoice).filter(Invoice.business_id == biz.id, Invoice.invoice_no == "IIQ-S2").first():
            s2 = Invoice(
                business_id=biz.id, party_id=party_map["Customer Maharashtra Corp"].id, direction="sales", source="generated",
                invoice_no="IIQ-S2", invoice_date=date(2025, 4, 15), due_date=date(2025, 5, 15),
                buyer_gstin="27BBBBB2222B1Z2", place_of_supply_state="27",
                taxable=4000000, cgst=0, sgst=0, igst=720000, cess=0, total=4720000,
                review_status="approved", payment_status="unpaid", validation_status="ok"
            )
            db.add(s2)
            db.flush()
            db.add(InvoiceItem(
                invoice_id=s2.id, description="Computing Hardware Units", hsn_sac="8471", quantity=2.0,
                unit="NOS", rate=2000000, taxable=4000000, gst_rate=18.0, cgst=0, sgst=0, igst=720000, amount=4720000
            ))

        # P1: Purchase, Karnataka, Taxable 25,000, CGST 2,250, SGST 2,250, Total 29,500
        if not db.query(Invoice).filter(Invoice.business_id == biz.id, Invoice.invoice_no == "IIQ-P1").first():
            p1 = Invoice(
                business_id=biz.id, party_id=party_map["Sharma Traders Bangalore"].id, direction="purchase", source="extracted",
                invoice_no="IIQ-P1", invoice_date=date(2025, 4, 20), due_date=date(2025, 5, 20),
                supplier_gstin="29CCCCC3333C1Z3", place_of_supply_state="29",
                taxable=2500000, cgst=225000, sgst=225000, igst=0, cess=0, total=2950000,
                review_status="approved", payment_status="unpaid", validation_status="ok"
            )
            db.add(p1)

        # P2: Purchase, Delhi, Taxable 5,000, IGST 900, Total 5,900
        if not db.query(Invoice).filter(Invoice.business_id == biz.id, Invoice.invoice_no == "IIQ-P2").first():
            p2 = Invoice(
                business_id=biz.id, party_id=party_map["Delhi Hardware Supplies"].id, direction="purchase", source="extracted",
                invoice_no="IIQ-P2", invoice_date=date(2025, 4, 25), due_date=date(2025, 5, 25),
                supplier_gstin="07DDDDD4444D1Z4", place_of_supply_state="07",
                taxable=500000, cgst=0, sgst=0, igst=90000, cess=0, total=590000,
                review_status="approved", payment_status="unpaid", validation_status="ok"
            )
            db.add(p2)

        db.commit()
        print("Demo dataset seeded successfully!")
        print("\nLogin credentials:")
        print("  Owner:      owner@demo.com / DemoPassword123!")
        print("  Accountant: accountant@demo.com / DemoPassword123!")
        print("  Staff:      staff@demo.com / DemoPassword123!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding demo data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
