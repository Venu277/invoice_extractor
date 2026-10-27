# Axion: Intelligent Indian Invoice Extraction & GST Platform

Axion is a modern, enterprise-grade invoice intelligence and statutory GST compliance platform tailored for Indian businesses and accounting teams. Powered by FastAPI, SQLAlchemy 2.0, and a server-rendered Jinja2 interface, Axion converts unstructured invoice PDFs, scans, and physical receipts into validated GST records.

Every downstream accounting function—ledger tracking, ageing analysis, accrual Profit & Loss, GSTR-1, GSTR-3B, HSN summaries, outgoing sales invoicing, and automated financial health alerts—operates directly on this verified pipeline.

---

## Key Capabilities

### 1. Robust Extraction Pipeline
- **Tiered Parser**: High-speed extraction through `pdfplumber` and `pypdf`, automatically falling back to Tesseract OCR when processing scanned documents.
- **Statutory GST Validation**: Validates 15-character GSTIN checksums, state code alignment, place of supply (Intra-state CGST+SGST vs. Inter-state IGST), line-item tax rates, and reverse charge applicability.
- **Day-First Indian Date Resolution**: Normalizes diverse date formats (DD/MM/YYYY, DD-MM-YYYY, DD Month YYYY) and resolves payment terms to exact due dates.

### 2. Workspace Management & Saved Collections
- **Current Invoices (Active Workspace)**: Dedicated view displaying invoices from the most recent upload session for review and batch approval.
- **Clear Workspace**: One-click option to clear the active workspace while preserving the entire table within a named, permanent collection.
- **Saved Collections**: Case-insensitive unique collection naming with month and year categorization, allowing accountants to organize invoices by filing periods or vendor batches.

### 3. Outgoing Sales Invoice Generator
- **Compliant Invoicing**: Generates clean sales invoices with automatic sequential numbering (`INV-YYYY-XXXX`).
- **Interactive Line Items**: Readable input fields with positive integer quantity enforcement, dynamic tax computation, and support for multi-rate GST.
- **PDF Generation**: Downloadable print-ready PDF invoices complete with bank payment details and UPI QR codes.

### 4. Statutory Reports & Watermarking
- **Filing Ready Summaries**: Monthly and quarterly reports for GSTR-1 (B2B, B2CL, B2CS) and GSTR-3B with legal tax set-off sequence (IGST -> CGST -> SGST).
- **Statutory PDF Report**: Prompts for filing month and year, inspects invoices in that period's collection, and renders a detailed audit PDF with the company's verified statutory watermark on the bottom right.
- **Multi-Format Exports**: Export ledgers and summaries in CSV, formatted Excel (`.xlsx`) with frozen headers, and Tally XML voucher formats.

### 5. Multi-Tenant Security & Authentication
- **Tenant Isolation**: Every database record is strictly isolated by `business_id` across all queries and services.
- **Argon2id Password Encryption**: Passwords secured using state-of-the-art Argon2id hashing with rate-limited brute-force lockout (5 attempts / 5 minutes).
- **Single-Use Password Recovery**: Dedicated "Forgot password?" option with token-based email dispatch, time-limited expiration, and direct dashboard access upon credential update.
- **Live Indian Calendar**: Dashboard header displaying real-time Indian Standard Time (IST) date, day of the week, and active Indian Financial Year (e.g., `FY 2026-27`).

---

## Architecture & Principles

1. **Extraction First**: Raw files undergo validation before entering the business ledger. Faulty or non-compliant invoices generate clear warnings without crashing ingestion.
2. **Paise Precision**: All monetary values are stored in the database as integer paise (`BigInteger`). Floating-point arithmetic is prohibited; Python computations utilize `Decimal` with line-level half-up rounding (`ROUND_HALF_UP`).
3. **Design System**: Built on a light green color palette (`#90cf8e`, `#a7dca5`, `#c6edc3`, `#e4fde1`, `#effdee`) using CSS custom design tokens for visual consistency and WCAG AA contrast compliance.

---

## Quickstart & Setup

### Prerequisites
- Python 3.11 or higher
- Git
- Tesseract OCR (Optional, required only for scanned receipts or image-based PDFs)

### Installation (PowerShell / Windows)

```powershell
# 1. Clone repository
git clone https://github.com/Venu277/invoice_extractor.git
cd invoice_extractor

# 2. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment settings
Copy-Item .env.example .env

# 5. Run database migrations
.\venv\Scripts\alembic.exe upgrade head

# 6. Seed demo dataset (parties, invoices, payments)
python scripts/seed_demo.py

# 7. Start development server
.\venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Installation (Linux / macOS / Bash)

```bash
# 1. Clone repository
git clone https://github.com/Venu277/invoice_extractor.git
cd invoice_extractor

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment settings
cp .env.example .env

# 5. Run database migrations
alembic upgrade head

# 6. Seed demo dataset
python scripts/seed_demo.py

# 7. Start server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## Access Points & Demo Accounts

Once the server is running:
- **Application Portal**: `http://localhost:8000`
- **Interactive OpenAPI Documentation**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`

### Pre-Configured Accounts (Demo Seed)

| Role | Email | Password | Permissions |
|---|---|---|---|
| Business Owner | `owner@demo.com` | `DemoPassword123!` | Full administrative access, backups, settings, reviews |
| Accountant | `accountant@demo.com` | `DemoPassword123!` | Invoices, reviews, collections, GST reports, exports |
| Staff | `staff@demo.com` | `DemoPassword123!` | Document upload, directory search, party records |

---

## Test Suite & Verification

The test suite validates foundation math, security boundaries, tenant isolation, OCR degradation, GST set-off rules, collections, and UI rendering across 38 integration test cases:

```powershell
# Run full test suite
.\venv\Scripts\pytest.exe -v
```

### Test Highlights
- `test_auth_and_tenant.py`: Multi-tenant isolation, Argon2id verification, brute-force lockouts.
- `test_collections.py`: Case-insensitive collection name uniqueness, collection retrieval.
- `test_forgot_password_and_clear_workspace.py`: Password recovery flow, single-use token lifecycle, workspace clearing.
- `test_gst_and_exports.py`: GSTR-1 B2B/B2CL/B2CS calculations, GSTR-3B tax set-off rules, Tally XML vouchers.
- `test_frontend_smoke.py`: Asset budgets, token-based color system compliance, zero emoji enforcement.

---

## Project Structure

```
invoice_extractor/
├── app/
│   ├── config.py              # Environment configuration & Pydantic settings
│   ├── db.py                  # SQLAlchemy engine & session management
│   ├── deps.py                # Dependency injection & role authentication
│   ├── extraction/            # OCR, PDF parsers, field regex, GST validation
│   ├── gst/                   # GSTR-1, GSTR-3B tax set-off rules, HSN summary
│   ├── models/                # SQLAlchemy database models (Invoice, User, Collection, etc.)
│   ├── routers/
│   │   ├── api/               # REST API endpoints (v1 auth, invoices, collections, reports)
│   │   └── web/               # Server-rendered Jinja2 view controllers
│   ├── schemas/               # Pydantic validation models
│   ├── services/              # Business logic (invoice, auth, reporting, payments, backups)
│   ├── static/                # CSS design tokens, JavaScript modules, SVG icons
│   └── templates/             # Jinja2 templates (dashboard, invoices, collections, auth)
├── data/                      # SQLite database storage (excluded from git)
├── scripts/                   # Seeder, migration helpers, visual audit scripts
├── tests/                     # Pytest automated test suite (38 test modules)
└── alembic.ini                # Alembic migration configuration
```

---

## License

This project is licensed under the MIT License.
