"""Database layer: user accounts and saved invoices (SQLite, built into Python)."""
import os
import re
import hmac
import sqlite3
import hashlib
from contextlib import closing
from datetime import datetime

import pandas as pd

DB_PATH = os.path.join("data", "invoices.db")

INVOICE_COLUMNS = ["id", "file", "vendor", "invoice_no", "date", "month", "gstin",
                   "subtotal", "cgst", "sgst", "igst", "gst_amount", "total", "status"]


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                salt          TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                file        TEXT,
                vendor      TEXT,
                invoice_no  TEXT,
                date        TEXT,
                month       TEXT,
                gstin       TEXT,
                subtotal    REAL,
                cgst        REAL,
                sgst        REAL,
                igst        REAL,
                gst_amount  REAL,
                total       REAL,
                status      TEXT,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )""")


# ---------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------
def _hash_password(password, salt_bytes):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 200_000).hex()


def create_user(business_name, email, password):
    """Returns (True, 'ok') or (False, 'reason')."""
    business_name = (business_name or "").strip()
    email = (email or "").strip().lower()
    password = password or ""

    if not business_name:
        return False, "Please enter your business name."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "Please enter a valid email address."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    salt = os.urandom(16)
    try:
        with closing(get_conn()) as conn, conn:
            conn.execute(
                "INSERT INTO users (business_name, email, salt, password_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (business_name, email, salt.hex(), _hash_password(password, salt),
                 datetime.now().isoformat(timespec="seconds")))
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists. Please log in."
    return True, "ok"


def authenticate(email, password):
    """Returns {'id', 'business_name', 'email'} if the login is correct, else None."""
    email = (email or "").strip().lower()
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        return None
    attempt = _hash_password(password or "", bytes.fromhex(row["salt"]))
    if hmac.compare_digest(attempt, row["password_hash"]):
        return {"id": row["id"], "business_name": row["business_name"], "email": row["email"]}
    return None


# ---------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------
def month_key(date_text):
    """'2025-03-12' -> '2025-03'. Returns None if the date is not in YYYY-MM-DD form."""
    if date_text and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date_text)):
        try:
            datetime.strptime(str(date_text), "%Y-%m-%d")
            return str(date_text)[:7]
        except ValueError:
            return None
    return None


def duplicate_key(vendor, invoice_no):
    """Two invoices are duplicates if vendor and invoice number are both the same."""
    if not vendor or not invoice_no:
        return None
    return (vendor.strip().lower(), invoice_no.strip().lower())


def existing_keys(user_id):
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT vendor, invoice_no FROM invoices WHERE user_id = ?",
                            (user_id,)).fetchall()
    keys = set()
    for r in rows:
        k = duplicate_key(r["vendor"], r["invoice_no"])
        if k:
            keys.add(k)
    return keys


def save_invoices(user_id, rows):
    """Saves extracted rows. Skips duplicates. Returns (saved_count, skipped_count)."""
    keys = existing_keys(user_id)
    saved = skipped = 0
    now = datetime.now().isoformat(timespec="seconds")
    with closing(get_conn()) as conn, conn:
        for r in rows:
            k = duplicate_key(r.get("vendor"), r.get("invoice_no"))
            if k and k in keys:
                skipped += 1
                continue
            conn.execute(
                "INSERT INTO invoices (user_id, file, vendor, invoice_no, date, month, gstin, "
                "subtotal, cgst, sgst, igst, gst_amount, total, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, r.get("file"), r.get("vendor"), r.get("invoice_no"), r.get("date"),
                 month_key(r.get("date")), r.get("gstin"), r.get("subtotal"), r.get("cgst"),
                 r.get("sgst"), r.get("igst"), r.get("gst_amount"), r.get("total"),
                 r.get("status"), now))
            if k:
                keys.add(k)
            saved += 1
    return saved, skipped


def get_invoices(user_id):
    """All invoices of one user as a pandas DataFrame (newest date first)."""
    with closing(get_conn()) as conn:
        df = pd.read_sql_query(
            f"SELECT {', '.join(INVOICE_COLUMNS)} FROM invoices WHERE user_id = ? "
            "ORDER BY date DESC, id DESC", conn, params=(user_id,))
    return df


def delete_invoice(user_id, invoice_id):
    with closing(get_conn()) as conn, conn:
        conn.execute("DELETE FROM invoices WHERE id = ? AND user_id = ?",
                     (int(invoice_id), user_id))