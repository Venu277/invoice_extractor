# InvoiceIQ Local Development Runner
Write-Host "Starting InvoiceIQ Development Server..." -ForegroundColor Cyan

$env:PYTHONPATH = "."
.\venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
