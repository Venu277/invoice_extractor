import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.user import User
from app.models.invoice import Invoice
from app.models.collection import InvoiceCollection
from app.services.security import verify_password


def test_forgot_password_and_reset_flow(client: TestClient, db_session: Session):
    """Test full forgot password link generation, token validation, password update, and dashboard access."""
    # 1. Sign up a new user
    signup_res = client.post("/api/v1/auth/signup", json={
        "business_name": "Reset Flow Corp",
        "owner_name": "Rohan Verma",
        "email": "rohan@resetcorp.com",
        "password": "OldPassword123!",
        "gstin": "29ABCDE9999F1Z9"
    })
    assert signup_res.status_code == 201

    # 2. Forgot password request for non-existent email
    fail_res = client.post("/auth/forgot-password", data={"email": "nonexistent@resetcorp.com"}, follow_redirects=False)
    assert fail_res.status_code == 303
    assert "error=" in fail_res.headers["location"]
    assert "No+account+found" in fail_res.headers["location"]

    # 3. Forgot password request for registered email
    success_res = client.post("/auth/forgot-password", data={"email": "rohan@resetcorp.com"}, follow_redirects=False)
    assert success_res.status_code == 303
    loc = success_res.headers["location"]
    assert "success=" in loc
    assert "reset_url=" in loc

    # 4. Check that token was stored in DB
    user = db_session.query(User).filter(User.email == "rohan@resetcorp.com").first()
    assert user is not None
    assert user.reset_token is not None
    assert user.reset_token_expires is not None
    token = user.reset_token

    # 5. Load reset password page with valid token
    page_res = client.get(f"/auth/reset-password?token={token}")
    assert page_res.status_code == 200
    assert "Assign New Password" in page_res.text
    assert "rohan@resetcorp.com" in page_res.text

    # 6. Load with invalid token -> redirects to login
    bad_page_res = client.get("/auth/reset-password?token=invalid_dummy_token", follow_redirects=False)
    assert bad_page_res.status_code == 303
    assert "/login" in bad_page_res.headers["location"]

    # 7. Submit mismatched passwords
    mismatch_res = client.post("/auth/reset-password", data={
        "token": token,
        "new_password": "BrandNewPassword123!",
        "confirm_password": "DifferentPassword123!"
    }, follow_redirects=False)
    assert mismatch_res.status_code == 303
    assert "error=Passwords+do+not+match" in mismatch_res.headers["location"]

    # 8. Submit matching new password
    submit_res = client.post("/auth/reset-password", data={
        "token": token,
        "new_password": "BrandNewPassword123!",
        "confirm_password": "BrandNewPassword123!"
    }, follow_redirects=False)
    assert submit_res.status_code == 303
    assert submit_res.headers["location"] == "/dashboard"
    assert "access_token" in submit_res.cookies

    # 9. Verify password updated in DB and token wiped
    db_session.refresh(user)
    assert user.reset_token is None
    assert user.reset_token_expires is None
    assert verify_password("BrandNewPassword123!", user.password_hash)

    # 10. Login with new password succeeds
    login_new = client.post("/api/v1/auth/login", json={
        "email": "rohan@resetcorp.com",
        "password": "BrandNewPassword123!"
    })
    assert login_new.status_code == 200

    # 11. Login with old password fails
    login_old = client.post("/api/v1/auth/login", json={
        "email": "rohan@resetcorp.com",
        "password": "OldPassword123!"
    })
    assert login_old.status_code == 401


def test_clear_workspace_and_saved_collections_flow(client: TestClient, db_session: Session):
    """Test clearing workspace invoices and verifying preservation in collections menu."""
    # 1. Sign up and login
    signup_res = client.post("/api/v1/auth/signup", json={
        "business_name": "Workspace Test Corp",
        "owner_name": "Karan Mehra",
        "email": "karan@workspacetest.com",
        "password": "Password123!"
    })
    assert signup_res.status_code == 201
    biz_id = signup_res.json()["business_id"]

    login_res = client.post("/api/v1/auth/login", json={
        "email": "karan@workspacetest.com",
        "password": "Password123!"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    cookies = {"access_token": token}

    # 2. Create sample invoices in workspace for this business
    inv1 = Invoice(
        business_id=biz_id,
        invoice_no="WS-INV-001",
        direction="purchase",
        total=500000,
        taxable=423728,
        in_workspace=True
    )
    inv2 = Invoice(
        business_id=biz_id,
        invoice_no="WS-INV-002",
        direction="sales",
        total=750000,
        taxable=635593,
        in_workspace=True
    )
    db_session.add_all([inv1, inv2])
    db_session.commit()
    inv1_id, inv2_id = inv1.id, inv2.id

    # 3. Verify they show in Current Invoices workspace
    current_view = client.get("/invoices?view=current", headers=headers, cookies=cookies)
    assert current_view.status_code == 200
    assert "WS-INV-001" in current_view.text
    assert "WS-INV-002" in current_view.text
    assert "Clear Workspace" in current_view.text

    # 4. Clear Workspace via API
    clear_res = client.post("/api/v1/collections/clear-workspace", json={
        "name": "Q3 Cleared Batch",
        "month": 10,
        "year": 2026,
        "invoice_ids": [inv1_id, inv2_id]
    }, headers=headers)
    assert clear_res.status_code == 201
    col_id = clear_res.json()["id"]

    # 5. Verify case-insensitive duplicate collection name rejection
    dup_res = client.post("/api/v1/collections/clear-workspace", json={
        "name": "q3 cleared batch",
        "month": 10,
        "year": 2026,
        "invoice_ids": []
    }, headers=headers)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.text.lower()

    # 6. Verify Current Invoices workspace is now clear!
    cleared_view = client.get("/invoices?view=current", headers=headers, cookies=cookies)
    assert cleared_view.status_code == 200
    assert "Workspace is Clear" in cleared_view.text
    assert "WS-INV-001" not in cleared_view.text
    assert "WS-INV-002" not in cleared_view.text

    # 7. Verify the exact invoices are saved and viewable in Collections menu
    collections_view = client.get("/invoices?view=collections", headers=headers, cookies=cookies)
    assert collections_view.status_code == 200
    assert "Q3 Cleared Batch" in collections_view.text

    # 8. Drill down into the specific saved collection
    col_detail_view = client.get(f"/invoices?view=collections&collection_id={col_id}", headers=headers, cookies=cookies)
    assert col_detail_view.status_code == 200
    assert "WS-INV-001" in col_detail_view.text
    assert "WS-INV-002" in col_detail_view.text
