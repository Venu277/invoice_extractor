import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.logging_config import setup_logging, request_id_ctx_var
from app.jobs.scheduler import start_scheduler, shutdown_scheduler

# Initialize logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure runtime directories exist, start scheduler
    from pathlib import Path
    Path("data").mkdir(parents=True, exist_ok=True)
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.LOG_DIR).mkdir(parents=True, exist_ok=True)

    start_scheduler()
    yield
    # Shutdown: Stop scheduler cleanly
    shutdown_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent Indian Invoice Data Extraction & GST Management Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Mount static directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# -------------------------------------------------------------
# Middlewares
# -------------------------------------------------------------
@app.middleware("http")
async def request_id_and_security_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_ctx_var.set(req_id)
    request.state.request_id = req_id

    try:
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id

        # Security Headers (Section 10)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
    finally:
        request_id_ctx_var.reset(token)


# -------------------------------------------------------------
# Global Exception Handlers
# Consistent Error Format: { "error": { "code": ..., "message": ..., "details": ... } }
# -------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api/") or "application/json" in request.headers.get("accept", ""):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                    "details": None,
                }
            },
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters",
                "details": exc.errors(),
            }
        },
    )


# -------------------------------------------------------------
# Health Check Endpoints
# -------------------------------------------------------------
@app.get("/health")
@app.get("/api/v1/health")
def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "version": "1.0.0"
    }


# -------------------------------------------------------------
# API Routers
# -------------------------------------------------------------
from app.routers.api import (
    auth, business, documents, invoices, parties,
    payments, ageing, dashboard, reports, alerts,
    gst, exports, generator, sharing, recurring, backups, collections
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(business.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(parties.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(ageing.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(gst.router, prefix="/api/v1")
app.include_router(exports.router, prefix="/api/v1")
app.include_router(generator.router, prefix="/api/v1")
app.include_router(sharing.router, prefix="/api/v1")
app.include_router(recurring.router, prefix="/api/v1")
app.include_router(backups.router, prefix="/api/v1")
app.include_router(collections.router, prefix="/api/v1")

# -------------------------------------------------------------
# Web Page Routers
# -------------------------------------------------------------
from app.routers.web import pages
app.include_router(pages.router)
