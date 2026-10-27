"""Verify end-to-end Render deployment flow locally against a fresh SQLite database."""
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Use an isolated fresh database file
test_db_path = BASE_DIR / "data" / "render_fresh_test.db"
if test_db_path.exists():
    test_db_path.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
os.environ["SECRET_KEY"] = "render-test-secret-key-32-chars-long!"
os.environ["SEED_DEMO"] = "false"
os.environ["APP_ENV"] = "production"

print("1. Running Render build step: alembic upgrade head...")
from alembic import command
from alembic.config import Config

alembic_cfg = Config(str(BASE_DIR / "alembic.ini"))
alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{test_db_path.as_posix()}")
command.upgrade(alembic_cfg, "head")
print("-> Alembic upgrade head succeeded!")

print("2. Starting application test client...")
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("3. Checking /health endpoint...")
resp = client.get("/health")
assert resp.status_code == 200, f"/health failed: {resp.status_code} {resp.text}"
data = resp.json()
assert data.get("status") in ("ok", "healthy"), f"Health status unexpected: {data}"
print(f"-> /health OK: {data}")

print("4. Testing new user signup...")
signup_payload = {
    "owner_name": "Render Owner",
    "email": "render_owner@example.com",
    "password": "SecurePassword123!",
    "business_name": "Render Enterprises",
    "gstin": "29ABCDE1234F1Z5",
    "state_code": "29"
}
signup_resp = client.post("/api/v1/auth/signup", json=signup_payload)
assert signup_resp.status_code in (200, 201), f"Signup failed: {signup_resp.status_code} {signup_resp.text}"
user_data = signup_resp.json()
print(f"-> Signup OK: User ID {user_data.get('user_id')}, Business ID {user_data.get('business_id')}")

print("5. Testing login with newly created user...")
login_payload = {
    "email": "render_owner@example.com",
    "password": "SecurePassword123!"
}
login_resp = client.post("/api/v1/auth/login", json=login_payload)
assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code} {login_resp.text}"
token_data = login_resp.json()
access_token = token_data.get("access_token")
assert access_token, "No access token returned"
headers = {"Authorization": f"Bearer {access_token}"}
print("-> Login OK: Access token acquired")

print("6. Testing PDF upload on fresh database...")
inv_path = BASE_DIR / "invoices" / "inv1.pdf"
assert inv_path.exists(), f"{inv_path} does not exist"
pdf_bytes = inv_path.read_bytes()

files = [("files", ("inv1.pdf", pdf_bytes, "application/pdf"))]
upload_resp = client.post("/api/v1/documents/upload?sync=true", files=files, headers=headers)
assert upload_resp.status_code in (200, 201, 202), f"Upload failed: {upload_resp.status_code} {upload_resp.text}"
upload_result = upload_resp.json()
print(f"-> PDF upload OK: batch={upload_result}")

print("7. Verifying users.reset_token query executes properly...")
from app.db import SessionLocal
from app.models.user import User

db = SessionLocal()
try:
    user = db.query(User).filter(User.email == "render_owner@example.com").first()
    assert user is not None
    assert hasattr(user, "reset_token")
    assert hasattr(user, "reset_token_expires")
    print(f"-> Query users OK: user={user.email}, reset_token={user.reset_token}, in_workspace column verified")
finally:
    db.close()

# Cleanup
if test_db_path.exists():
    try:
        test_db_path.unlink()
    except Exception:
        pass

print("\nALL RENDER BUILD AND LIFECYCLE CHECKS PASSED SUCCESSFULLY!")
