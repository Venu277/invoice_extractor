import os
import re
import pytest
from starlette.testclient import TestClient

def test_public_homepage_renders(client: TestClient):
    """Smoke test: public homepage /home and auth page /login render branding and layout sections."""
    home_res = client.get("/home")
    assert home_res.status_code == 200
    home_html = home_res.text
    assert "Axion" in home_html
    assert "Invoice intelligence for growing businesses" in home_html
    assert "What Axion Does" in home_html
    assert "Privacy Policy" in home_html

    login_res = client.get("/login")
    assert login_res.status_code == 200
    login_html = login_res.text
    assert "Axion" in login_html
    assert "tab-login" in login_html
    assert "tab-signup" in login_html
    assert "tab-recover" in login_html
    assert 'action="/auth/login"' in login_html
    assert 'action="/auth/signup"' in login_html
    assert "Privacy Policy" in login_html


def test_authenticated_routes_render_axion_shell(client: TestClient):
    """Smoke test: core authenticated app routes render with Axion base layout."""
    # Sign up and log in
    signup_payload = {
        "business_name": "Axion Frontend Smoke Corp",
        "owner_name": "Design Tester",
        "email": "tester_smoke@axionfront.com",
        "password": "Password123!",
        "gstin": "29AABCA1234A1Z1"
    }
    sign_res = client.post("/api/v1/auth/signup", json=signup_payload)
    assert sign_res.status_code == 201

    login_res = client.post("/api/v1/auth/login", json={
        "email": "tester_smoke@axionfront.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    routes = [
        "/dashboard",
        "/upload",
        "/invoices",
        "/invoices/new",
        "/parties",
        "/reports",
        "/exports",
        "/alerts",
        "/settings",
    ]

    for route in routes:
        res = client.get(route, headers={"Authorization": f"Bearer {token}"}, cookies={"access_token": token})
        assert res.status_code == 200, f"Route {route} returned status {res.status_code}"
        html = res.text
        # Base shell presence
        assert "sidebar" in html, f"Sidebar missing on route {route}"
        assert "Axion" in html, f"Axion mark missing on route {route}"
        assert "tokens.css" in html, f"tokens.css missing on route {route}"


def test_no_emojis_in_frontend_templates():
    """Smoke test: verify no emojis or arrow/check text characters in any template."""
    pattern = re.compile(r'(&[rlud]arr;|[←→↑↓✓✔✕✖]|[\U00010000-\U0010ffff]|[\u2600-\u27bf])')
    template_dir = os.path.join(os.path.dirname(__file__), "..", "app", "templates")

    violations = []
    for root, _, files in os.walk(template_dir):
        for f in files:
            if f.endswith('.html'):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                    for line_no, line in enumerate(fp, 1):
                        matches = pattern.findall(line)
                        if matches:
                            violations.append(f"{f}:{line_no} -> {matches}")

    assert len(violations) == 0, f"Found forbidden emoji/symbol characters in templates: {violations}"


def test_frontend_asset_budgets():
    """Smoke test: verify static asset budgets (CSS < 60KB, JS < 40KB)."""
    base_dir = os.path.join(os.path.dirname(__file__), "..", "app", "static")

    # CSS budget
    css_dir = os.path.join(base_dir, "css")
    css_total = sum(os.path.getsize(os.path.join(css_dir, f)) for f in os.listdir(css_dir) if f.endswith(".css"))
    assert css_total < 60 * 1024, f"CSS exceeds 60 KB budget: {css_total} bytes ({css_total/1024:.2f} KB)"

    # JS budget (excluding external libraries like Chart.js)
    js_dir = os.path.join(base_dir, "js")
    js_total = sum(os.path.getsize(os.path.join(js_dir, f)) for f in os.listdir(js_dir) if f.endswith(".js"))
    assert js_total < 40 * 1024, f"Own JS exceeds 40 KB budget: {js_total} bytes ({js_total/1024:.2f} KB)"


def test_no_hex_or_white_outside_tokens_css():
    """Step 5 test: fails if any template, CSS or JS file contains a white or hex colour literal outside tokens.css."""
    base_dir = os.path.join(os.path.dirname(__file__), "..", "app")
    target_dirs = [os.path.join(base_dir, "templates"), os.path.join(base_dir, "static", "css"), os.path.join(base_dir, "static", "js")]

    hex_or_white_pattern = re.compile(r'(#[0-9a-fA-F]{3,8}|(?<!-)\bwhite\b)', re.IGNORECASE)
    violations = []

    for d in target_dirs:
        for root, _, files in os.walk(d):
            for f in files:
                if f == "tokens.css":
                    continue
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                    for line_no, line in enumerate(fp, 1):
                        # Filter out CSS 'white-space' property
                        cleaned_line = re.sub(r'white-space', '', line)
                        matches = hex_or_white_pattern.findall(cleaned_line)
                        if matches:
                            violations.append(f"{f}:{line_no} -> {matches} in: {line.strip()[:60]}")

    assert len(violations) == 0, f"Found hex or white color literals outside tokens.css: {violations}"
