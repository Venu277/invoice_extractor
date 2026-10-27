from datetime import date
from pathlib import Path
import pytest
from app.services.report_pdf_service import generate_monthly_report_pdf


def test_profit_and_loss_accrual_basis(client):
    # Signup owner
    client.post("/api/v1/auth/signup", json={
        "business_name": "P&L Test Biz",
        "owner_name": "PnL Owner",
        "email": "pnl@biz.com",
        "password": "Password123!",
        "gstin": "29ABCDE1234F1Z5"
    })
    token = client.post("/api/v1/auth/login", json={
        "email": "pnl@biz.com",
        "password": "Password123!"
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Upload inv1.pdf (Sharma Traders, taxable = Rs. 10,000 = 1000000 paise, purchase)
    pdf_bytes1 = Path("invoices/inv1.pdf").read_bytes()
    client.post("/api/v1/documents/upload?sync=true", headers=headers, files=[("files", ("inv1.pdf", pdf_bytes1, "application/pdf"))])

    invs = client.get("/api/v1/invoices", headers=headers).json()
    assert len(invs) >= 1
    inv1_id = invs[0]["id"]
    client.put(f"/api/v1/invoices/{inv1_id}", headers=headers, json={"direction": "purchase"})
    client.post(f"/api/v1/invoices/{inv1_id}/approve", headers=headers)

    # Check P&L
    pnl = client.get("/api/v1/reports/profit-and-loss", headers=headers).json()
    assert pnl["expenses"]["purchase_count"] == 1
    assert pnl["expenses"]["taxable"] == 1000000
    assert pnl["income"]["taxable"] == 0
    assert pnl["net_profit"] == -1000000


def test_dashboard_and_insights(client):
    client.post("/api/v1/auth/signup", json={
        "business_name": "Dashboard Biz",
        "owner_name": "Dash Owner",
        "email": "dash@biz.com",
        "password": "Password123!"
    })
    token = client.post("/api/v1/auth/login", json={
        "email": "dash@biz.com",
        "password": "Password123!"
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    dash = client.get("/api/v1/dashboard", headers=headers).json()
    assert "sales_total" in dash
    assert "purchase_total" in dash
    assert "insights" in dash
    assert isinstance(dash["insights"], list)
    assert "alerts" in dash


def test_monthly_pdf_report(client):
    client.post("/api/v1/auth/signup", json={
        "business_name": "PDF Report Biz",
        "owner_name": "PDF Owner",
        "email": "pdf@biz.com",
        "password": "Password123!"
    })
    token = client.post("/api/v1/auth/login", json={
        "email": "pdf@biz.com",
        "password": "Password123!"
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Upload inv1.pdf (dated 12/03/2025 -> 2025-03)
    pdf_bytes = Path("invoices/inv1.pdf").read_bytes()
    client.post("/api/v1/documents/upload?sync=true", headers=headers, files=[("files", ("inv1.pdf", pdf_bytes, "application/pdf"))])
    invs = client.get("/api/v1/invoices", headers=headers).json()
    client.post(f"/api/v1/invoices/{invs[0]['id']}/approve", headers=headers)

    res = client.get("/api/v1/reports/monthly-pdf?month=2025-03", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")
