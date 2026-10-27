from datetime import datetime, timedelta
import pytest
from app.models.user import User


def test_signup_and_login_flow(client):
    # 1. Signup Business A
    res = client.post("/api/v1/auth/signup", json={
        "business_name": "Alpha Corp",
        "owner_name": "Alice Owner",
        "email": "alice@alpha.com",
        "password": "Password123!",
        "gstin": "29ABCDE1234F1Z5"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["business_id"] > 0
    assert data["recovery_code"] is not None
    recovery_code = data["recovery_code"]

    # 2. Login with correct password
    login_res = client.post("/api/v1/auth/login", json={
        "email": "alice@alpha.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    token = login_data["access_token"]
    assert token is not None
    assert login_data["role"] == "owner"
    assert "access_token" in login_res.cookies

    # 3. Access authenticated endpoint using Bearer token
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "alice@alpha.com"

    # 4. Access authenticated endpoint using Cookie
    cookie_res = client.get("/api/v1/auth/me", cookies={"access_token": token})
    assert cookie_res.status_code == 200
    assert cookie_res.json()["name"] == "Alice Owner"


def test_account_lockout_after_5_failed_attempts(client):
    # Signup a new user
    client.post("/api/v1/auth/signup", json={
        "business_name": "Lockout Biz",
        "owner_name": "Bob Lock",
        "email": "bob@lockout.com",
        "password": "CorrectPassword123!"
    })

    # Attempt 5 wrong logins
    for _ in range(5):
        fail_res = client.post("/api/v1/auth/login", json={
            "email": "bob@lockout.com",
            "password": "WrongPassword!"
        })
        assert fail_res.status_code == 401

    # 6th attempt should be locked out (429 Too Many Requests)
    locked_res = client.post("/api/v1/auth/login", json={
        "email": "bob@lockout.com",
        "password": "CorrectPassword123!"
    })
    assert locked_res.status_code == 429
    err_body = locked_res.json()
    msg = err_body.get("error", {}).get("message", err_body.get("detail", ""))
    assert "locked" in msg.lower()


def test_recovery_code_password_reset(client):
    # Signup
    signup_res = client.post("/api/v1/auth/signup", json={
        "business_name": "Recovery Biz",
        "owner_name": "Charlie",
        "email": "charlie@recovery.com",
        "password": "OldPassword123!"
    })
    recovery_code = signup_res.json()["recovery_code"]

    # Reset password with recovery code
    reset_res = client.post("/api/v1/auth/recovery-reset", json={
        "email": "charlie@recovery.com",
        "recovery_code": recovery_code,
        "new_password": "NewSecretPassword456!"
    })
    assert reset_res.status_code == 200
    new_recovery_code = reset_res.json()["new_recovery_code"]
    assert new_recovery_code != recovery_code

    # Old password fails
    old_login = client.post("/api/v1/auth/login", json={
        "email": "charlie@recovery.com",
        "password": "OldPassword123!"
    })
    assert old_login.status_code == 401

    # New password succeeds
    new_login = client.post("/api/v1/auth/login", json={
        "email": "charlie@recovery.com",
        "password": "NewSecretPassword456!"
    })
    assert new_login.status_code == 200


def test_role_permissions_and_tenant_isolation(client):
    # 1. Create Business Alpha (Owner)
    s1 = client.post("/api/v1/auth/signup", json={
        "business_name": "Alpha Corp",
        "owner_name": "Alpha Owner",
        "email": "owner@alpha.com",
        "password": "Password123!"
    })
    alpha_biz_id = s1.json()["business_id"]
    token_alpha_owner = client.post("/api/v1/auth/login", json={
        "email": "owner@alpha.com",
        "password": "Password123!"
    }).json()["access_token"]

    # 2. Alpha Owner creates Staff member
    staff_res = client.post(
        "/api/v1/auth/team",
        headers={"Authorization": f"Bearer {token_alpha_owner}"},
        json={
            "name": "Alpha Staff",
            "email": "staff@alpha.com",
            "password": "Password123!",
            "role": "staff"
        }
    )
    assert staff_res.status_code == 201

    token_alpha_staff = client.post("/api/v1/auth/login", json={
        "email": "staff@alpha.com",
        "password": "Password123!"
    }).json()["access_token"]

    # 3. Staff attempts to update business profile -> 403 Forbidden
    forbidden_update = client.put(
        "/api/v1/business/profile",
        headers={"Authorization": f"Bearer {token_alpha_staff}"},
        json={"name": "Hacked Alpha"}
    )
    assert forbidden_update.status_code == 403

    # 4. Staff attempts to add another team member -> 403 Forbidden
    forbidden_team = client.post(
        "/api/v1/auth/team",
        headers={"Authorization": f"Bearer {token_alpha_staff}"},
        json={
            "name": "Fake Member",
            "email": "fake@alpha.com",
            "password": "Password123!",
            "role": "staff"
        }
    )
    assert forbidden_team.status_code == 403

    # 5. Create Business Beta (Separate Tenant)
    s2 = client.post("/api/v1/auth/signup", json={
        "business_name": "Beta Ltd",
        "owner_name": "Beta Owner",
        "email": "owner@beta.com",
        "password": "Password123!"
    })
    beta_biz_id = s2.json()["business_id"]
    assert beta_biz_id != alpha_biz_id

    token_beta_owner = client.post("/api/v1/auth/login", json={
        "email": "owner@beta.com",
        "password": "Password123!"
    }).json()["access_token"]

    # 6. Verify Tenant Isolation: Beta owner only sees Beta profile, cannot see Alpha team
    beta_profile = client.get(
        "/api/v1/business/profile",
        headers={"Authorization": f"Bearer {token_beta_owner}"}
    ).json()
    assert beta_profile["id"] == beta_biz_id
    assert beta_profile["name"] == "Beta Ltd"

    beta_team = client.get(
        "/api/v1/auth/team",
        headers={"Authorization": f"Bearer {token_beta_owner}"}
    ).json()
    # Beta team contains only Beta members (1 owner), no Alpha members
    assert len(beta_team) == 1
    assert beta_team[0]["email"] == "owner@beta.com"
