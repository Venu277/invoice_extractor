import pytest
from starlette.testclient import TestClient


def test_invoice_collections_crud_and_case_insensitive_uniqueness(client: TestClient):
    # 1. Sign up and authenticate
    signup_payload = {
        "business_name": "Axion Collection Test Corp",
        "owner_name": "Collector Tester",
        "email": "collector@test.com",
        "password": "Password123!",
        "gstin": "29AABCA9999A1Z1"
    }
    sign_res = client.post("/api/v1/auth/signup", json=signup_payload)
    assert sign_res.status_code == 201

    login_res = client.post("/api/v1/auth/login", json={
        "email": "collector@test.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create first collection
    create_payload = {
        "name": "October 2026 Marketing Bills",
        "month": 10,
        "year": 2026,
        "invoice_ids": []
    }
    res = client.post("/api/v1/collections", json=create_payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "October 2026 Marketing Bills"
    assert data["month"] == 10
    assert data["year"] == 2026
    col_id = data["id"]

    # 3. Test case-insensitive duplicate rejection
    dup_payload = {
        "name": "october 2026 marketing bills",  # lower case duplicate!
        "month": 10,
        "year": 2026,
        "invoice_ids": []
    }
    dup_res = client.post("/api/v1/collections", json=dup_payload, headers=headers)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.text.lower()

    # 4. Another case variation check (uppercase)
    dup_upper = {
        "name": "OCTOBER 2026 MARKETING BILLS",
        "month": 11,
        "year": 2026,
        "invoice_ids": []
    }
    dup_upper_res = client.post("/api/v1/collections", json=dup_upper, headers=headers)
    assert dup_upper_res.status_code == 400

    # 5. List collections
    list_res = client.get("/api/v1/collections", headers=headers)
    assert list_res.status_code == 200
    cols = list_res.json()
    assert len(cols) == 1
    assert cols[0]["name"] == "October 2026 Marketing Bills"

    # 6. Get collection by id
    get_res = client.get(f"/api/v1/collections/{col_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == col_id
