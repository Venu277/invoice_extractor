Axion

Intelligent invoice extraction and GST management for small Indian businesses.

Show Image Show Image Show Image Show Image Show Image

Axion reads invoice PDFs and scans, extracts the supplier, dates, GSTIN, taxes and line items, checks them against GST rules, and files them into one clean ledger. Everything else (payables and receivables, ageing, profit and loss, GSTR summaries, sales invoicing, Tally exports) runs on that verified data, so the numbers you see are the numbers on your invoices.

<!-- Live demo: add your Render URL here, for example: **Live demo:** https://your-service.onrender.com -->
Contents
Why Axion
Features
How it works
Tech stack
Getting started
Demo accounts
Configuration
Deploying to Render
API
Testing
Project structure
Troubleshooting
Limitations and roadmap
Contributing
License
Why Axion

Small businesses receive invoices as PDFs, scans and phone photos, then retype them into spreadsheets. It is slow, mistakes creep in, and GST errors usually surface only at filing time. Axion extracts the data as invoices arrive, checks it straight away, and keeps everything in one organised place, so you always know who owes you, what you owe, and where your GST stands.

<!-- ## Screenshots Add images to docs/screenshots/ and uncomment this section. | Dashboard | Invoice review | |---|---| | ![Dashboard](docs/screenshots/dashboard.png) | ![Review](docs/screenshots/review.png) | -->
Features
Extraction and validation
Tiered reading. Text PDFs are read with pdfplumber and pypdf. Scanned documents fall back to Tesseract OCR automatically.
Fields extracted. Supplier, invoice number, invoice and due dates, GSTIN, place of supply, taxable value, CGST, SGST, IGST, totals, and line items with HSN or SAC codes.
Indian date handling. Day-first dates (DD/MM/YYYY, DD-MM-YYYY, 15 Mar 2025) are normalised, and payment terms are resolved to exact due dates.
GST checks. GSTIN format and state code, CGST and SGST equality, intra-state (CGST plus SGST) versus inter-state (IGST) tax, standard tax rates, and subtotal plus tax equals total. Problems show as warnings or errors and never stop an upload.
Duplicate detection. The same supplier and invoice number, or the same file, is flagged.
Review and workflow
Review screen. Check the original document beside editable fields, fix anything misread, then approve or reject. Only approved invoices count in reports.
Bulk upload. Upload several PDFs at once, or a ZIP archive of invoices.
Workspace and collections. The Current Invoices view shows the latest upload session. Clear the workspace in one click while keeping everything in a named, permanent collection. Collection names are unique (case-insensitive) and grouped by month and year.
Money tracking
Payments and status. Record full or partial payments. Status updates automatically (unpaid, partly paid, paid), and overdue invoices are highlighted.
Ageing. Receivables and payables are grouped into not due, 1 to 30, 31 to 60, 61 to 90, and 90+ days.
Parties. A directory of vendors and customers with payment terms and credit limits, and a ledger for each party.
Dashboard. Sales revenue with month-on-month change, purchases and expenses, net GST liability, pending reviews, receivables and payables with ageing bars, plain-language insights, active alerts, and top vendors and customers.
Alerts. Overdue and due-soon invoices, validation problems, and GST filing reminders (GSTR-1 on the 11th and GSTR-3B on the 20th by default, configurable).
Indian calendar. The header shows today's date in IST and the active financial year, for example FY 2026-27.
Reports and GST
Profit and loss. Accrual basis, from approved sales and purchase invoices.
GSTR-1 style summary. B2B, B2CL and B2CS.
GSTR-3B style summary. Output tax, input tax credit, and net payable, with the statutory set-off order (IGST, then CGST, then SGST).
HSN summary. Quantity, taxable value and tax grouped by HSN or SAC code.
PDF reports. A monthly business report, and a statutory report for a chosen filing month with a watermark.

The figures are working numbers for decision-making and reconciliation. They are not official filing forms and not tax advice.

Sales invoicing
Generate GST invoices with automatic sequential numbering (INV-YYYY-XXXX).
Multi-rate line items with automatic tax computation.
Print-ready PDF with your bank details and a UPI QR code.
Exports and backups
CSV and formatted Excel (.xlsx) registers with frozen headers.
Tally Prime XML with party ledger masters and balanced sales and purchase vouchers. Ledger names are configurable.
Accountant package (ZIP) with the original invoice PDFs, Excel registers, GSTR summaries, profit and loss, and an index file.
Backups from the Settings page.
Teams and security
Roles. Owner, accountant and staff, each with their own permissions (see Demo accounts).
Tenant isolation. Every record belongs to a business, and every query is filtered by business_id.
Passwords. Argon2id hashing, with lockout after 5 failed attempts in 5 minutes.
Recovery. A single-use, time-limited reset token sent by email (requires the optional SMTP settings).
Interface

Dark mode with a red palette, liquid-glass panels, squircle corners and a collapsible sidebar. All colours, radii and spacing come from CSS design tokens, with no emojis anywhere. See README_FRONTEND.md for how to change colours, copy and contact details.

How it works
Upload PDF, scan or ZIP
Read textpdfplumber, pypdf, OCR
Extract fieldssupplier, dates, GSTIN,taxes, line items
ValidateGSTIN, state, tax split, rates,totals
Review and approve
Approved ledger
Dashboard, ageing, alerts
GST reports and profit andloss
Exports: Tally, Excel, CSV, ZIP

Design principles

Extraction first. Files are validated before they enter the ledger. A faulty invoice produces a clear warning and never crashes ingestion.
Paise precision. Money is stored as integer paise. Calculations use Python Decimal with half-up rounding at line level, and floating-point maths is not used.
Strict tenant isolation. One business can never read or change another's data, and tests prove it.
Layered code. Routers (web and API) call services, and services call models. The web pages and the REST API use the same service functions.
Tech stack
Layer	Technology
Backend	FastAPI, Uvicorn
Database	SQLAlchemy 2.0 and Alembic. SQLite locally, PostgreSQL in production (psycopg2)
Validation and settings	Pydantic v2, pydantic-settings
Extraction	pdfplumber, pypdf, pytesseract, pdf2image (needs Tesseract and Poppler)
Reports and exports	ReportLab (PDF), openpyxl (Excel), Tally XML
Security	argon2-cffi (Argon2id), PyJWT
Background jobs	APScheduler
Frontend	Jinja2 templates, CSS design tokens, vanilla JavaScript
Tests	pytest, httpx
Getting started
Prerequisites
Python 3.11 or newer
Git
Optional, for scanned invoices only: Tesseract OCR and Poppler. On Windows, install both and either add them to PATH or set TESSERACT_CMD and POPPLER_PATH in .env. Without them, text PDFs still work and scans show a clear message.
Windows (PowerShell)
powershell
# 1. Clone the repository
git clone https://github.com/Venu277/invoice_extractor.git
cd invoice_extractor

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your settings file
Copy-Item .env.example .env

# 5. Create the database tables
alembic upgrade head

# 6. (Optional) Load demo data
python scripts/seed_demo.py

# 7. Start the server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

If PowerShell blocks the activation script, run Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned once and try again.

macOS and Linux
bash
git clone https://github.com/Venu277/invoice_extractor.git
cd invoice_extractor

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python scripts/seed_demo.py        # optional demo data
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

Then open:

What	Address
Application	http://localhost:8000
Interactive API docs (Swagger)	http://localhost:8000/docs
ReDoc	http://localhost:8000/redoc
Health check	http://localhost:8000/health

No demo data? Use Sign up on the home page. Creating an account also creates your business, and you become its owner.

Demo accounts

Created only when you run python scripts/seed_demo.py on your own machine. They are never created in production.

Role	Email	Password	Can do
Owner	owner@demo.com	DemoPassword123!	Everything, including settings, team and backups
Accountant	accountant@demo.com	DemoPassword123!	Invoices, reviews, collections, GST reports, exports
Staff	staff@demo.com	DemoPassword123!	Upload documents, search the directory, view party records
Configuration

Settings are read from environment variables or a .env file. Copy .env.example to start.

Variable	Purpose	Default
APP_NAME	Application name	Axion
APP_ENV	development or production	development
DEBUG	Debug mode, keep false in production	true
DATABASE_URL	Database connection. postgres:// and postgresql:// are converted to postgresql+psycopg2:// automatically	sqlite:///./data/app.db
SECRET_KEY	Random string of 32 or more characters used for signing. Generate one with openssl rand -hex 32	none, must be set
ALGORITHM	JWT signing algorithm	HS256
ACCESS_TOKEN_EXPIRE_MINUTES	Login session length	720
UPLOAD_DIR	Where uploaded invoice files are stored	./uploads
LOG_DIR	Where log files are written	./logs
BACKUP_DIR	Where backups are written	./backups
OCR_ENABLED	Turn OCR on or off	true
TESSERACT_CMD, POPPLER_PATH	Paths to the OCR tools if they are not on PATH	empty
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_TLS	Email settings for password recovery (optional)	empty, port 587, TLS on
GST_GSTR1_DUE_DAY, GST_GSTR3B_DUE_DAY	Day of month used for filing reminders	11, 20
TALLY_LEDGER_*	Ledger names used in the Tally export (Purchase, Sales, Input and Output CGST, SGST, IGST, Round Off)	the names shown in .env.example
SEED_DEMO	Whether to create demo data. Keep false in production	false
Deploying to Render

The repository includes a render.yaml blueprint for a single web service (axion-invoice-platform, free plan, Singapore region, Python 3.11.9).

Push the repository to GitHub.
In Render, choose New, then Blueprint, and select the repository.
Create a PostgreSQL database in Render. The blueprint does not create one. Copy its Internal Database URL and paste it into the service's DATABASE_URL variable.
Deploy. SECRET_KEY is generated for you, and SEED_DEMO is false.
Open the service URL and use Sign up to create your first account.

The blueprint runs these commands, which you can also enter manually:

Setting	Value
Build command	pip install -r requirements.txt && alembic upgrade head
Start command	uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health check path	/health

Things to know about hosting

Use PostgreSQL. Render's local disk is wiped on every deploy, so SQLite data would be lost.
Uploaded files are stored in UPLOAD_DIR, also on that disk. To keep them across deploys, attach a Render persistent disk (a paid feature), mount it, and set UPLOAD_DIR to its path.
OCR. Tesseract and Poppler are not preinstalled on Render's standard Python runtime, so scanned invoices need a Docker-based deploy, or run locally. Text PDFs work normally.
Backups. The in-app file backup is for SQLite. On PostgreSQL, rely on Render's database backups.
Free plan. The service may sleep when idle, so the first request after a pause can be slow.
API

Every feature in the web interface is also available through the REST API under /api/v1. Browse and try every endpoint at /docs. Sessions use JWT, and the same role permissions apply to the API and the web pages.

Testing
bash
pytest -v

The suite covers money maths, tenant isolation, authentication and lockout, OCR degradation, extraction and GST rules, collections, exports, migrations and the frontend. Highlights:

Test file	What it protects
test_auth_and_tenant.py	Tenant isolation, Argon2id verification, lockout
test_collections.py	Case-insensitive collection names, retrieval
test_forgot_password_and_clear_workspace.py	Password reset token lifecycle, clearing the workspace
test_gst_and_exports.py	GSTR-1 and GSTR-3B maths, set-off rules, Tally XML
test_frontend_smoke.py	Pages render, design tokens used, no emojis
test_migrations.py	Models and Alembic migrations stay in sync
Project structure
invoice_extractor/
├── app/
│   ├── main.py             # FastAPI application entry point
│   ├── config.py           # Settings (pydantic-settings)
│   ├── db.py               # Engine and session management
│   ├── deps.py             # Dependencies and role checks
│   ├── extraction/         # PDF reading, OCR, field extraction, GST validation
│   ├── gst/                # GSTR-1, GSTR-3B set-off, HSN summary
│   ├── jobs/               # Scheduled background jobs
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Business logic (shared by web and API)
│   ├── routers/
│   │   ├── api/            # REST API (/api/v1)
│   │   └── web/            # Server-rendered pages
│   ├── static/             # CSS tokens, JavaScript, SVG icons
│   └── templates/          # Jinja2 templates
├── migrations/             # Alembic migrations
├── scripts/                # Demo seeder and helper scripts
├── tests/                  # Automated tests
├── invoices/               # Sample invoice PDFs
├── legacy/                 # Original extraction code the engine was ported from
├── alembic.ini             # Migration configuration
├── pytest.ini              # Test configuration
├── render.yaml             # Render blueprint
├── requirements.txt        # Python dependencies
├── .env.example            # Settings template
└── README_FRONTEND.md      # Frontend and theming guide

The Python files in the repository root (app.py, database.py, extractor.py, processing.py, report.py, make_sample_invoices.py) belong to the early Streamlit prototype. They are kept for reference and are not used by the application in app/. The data/, uploads/, logs/ and backups/ folders are created at runtime and are not tracked in git.

Troubleshooting
Problem	Fix
no such column or a missing table after pulling new code	Run alembic upgrade head to bring the database up to date
ModuleNotFoundError	Activate the virtual environment and run pip install -r requirements.txt
Scanned invoices are not read	Install Tesseract and Poppler, set TESSERACT_CMD and POPPLER_PATH, and check OCR_ENABLED=true
Old styles after an update	Hard refresh the browser with Ctrl + F5
PowerShell will not activate the virtual environment	Run Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned once
Render build fails on a missing column	Make sure the build command includes alembic upgrade head, and that SEED_DEMO is false
Limitations and roadmap
Extraction depends on invoice layout. Unusual layouts may need a correction on the review screen, and line-item extraction is best effort.
OCR accuracy depends on scan quality.
The tax rate check flags invoices whose blended rate is not a standard slab, which can include genuine mixed-rate invoices.
GST reports are working figures, not official filing forms.
Ideas for later: bank statement matching, credit and debit notes, an audit trail, manual expense entry, quotations, a cash-flow forecast, and an email-in inbox.
Contributing

Contributions are welcome.

Fork the repository and create a branch for your change.
Run pytest and make sure everything passes.
Open a pull request that explains what changed and why.

Please do not commit .env files, database files or real invoices.

License

Released under the MIT License.
