from decimal import Decimal
from app.services.money import (
    rupees_to_paise,
    paise_to_decimal,
    round_half_up,
    format_inr
)
from app.models.business import Business


def test_health_endpoints(client):
    res1 = client.get("/health")
    assert res1.status_code == 200
    assert res1.json()["status"] == "ok"

    res2 = client.get("/api/v1/health")
    assert res2.status_code == 200
    assert res2.json()["status"] == "ok"


def test_security_headers_and_request_id(client):
    res = client.get("/health")
    assert "X-Request-ID" in res.headers
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["X-XSS-Protection"] == "1; mode=block"


def test_money_calculations_and_formatting():
    # 1. Non-negotiable rule 2: Money is never a float. Store integer paise.
    assert rupees_to_paise("123.45") == 12345
    assert rupees_to_paise(Decimal("123.456")) == 12346  # Round half-up
    assert rupees_to_paise(100) == 10000

    # 2. Decimal conversion
    assert paise_to_decimal(12345) == Decimal("123.45")

    # 3. Round half-up line level
    assert round_half_up(Decimal("10.005"), 2) == Decimal("10.01")
    assert round_half_up(Decimal("10.004"), 2) == Decimal("10.00")

    # 4. Indian number formatting
    # Rs. 1,23,456.00
    assert format_inr(12345600) == "Rs. 1,23,456.00"
    assert format_inr(0) == "Rs. 0.00"
    assert format_inr(500) == "Rs. 5.00"
    assert format_inr(10000000) == "Rs. 1,00,000.00"
    assert format_inr(1000000000) == "Rs. 1,00,00,000.00"


def test_db_session_and_model(db_session):
    biz = Business(name="Acme Corp", gstin="29ABCDE1234F1Z5", state_code="29")
    db_session.add(biz)
    db_session.commit()
    db_session.refresh(biz)

    assert biz.id is not None
    assert biz.name == "Acme Corp"
    assert biz.fy_start_month == 4
    assert biz.default_payment_terms_days == 30
