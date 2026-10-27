import secrets
import urllib.parse
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Request, Response, Form, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role, get_token_from_request
from app.models.user import User
from app.models.invoice import Invoice
from app.models.party import Party
from app.models.backup import Backup
from app.models.alert import Alert
from app.models.collection import InvoiceCollection
from app.schemas.auth import SignupRequest
from app.services.auth_service import signup_business, authenticate_user, reset_password_with_recovery_code, list_team_members
from app.services.security import hash_password, create_access_token
from app.services.business_service import get_business_by_id
from app.services.dashboard_service import get_dashboard_data
from app.services.invoice_service import list_invoices, get_invoice
from app.services.party_service import list_parties, get_party
from app.services.payment_service import get_party_ledger
from app.services.profit_loss_service import compute_profit_and_loss
from app.services.ageing_service import compute_ageing_report
from app.gst.summaries import compute_gstr3b_summary, compute_hsn_summary
from app.services.share_service import get_active_share_link, send_password_reset_email
from app.services.report_pdf_service import generate_monthly_report_pdf
from app.services.invoice_generator_service import generate_sales_invoice_pdf
from app.services.money import format_inr, paise_to_decimal

router = APIRouter(tags=["Web Pages"])
templates = Jinja2Templates(directory="app/templates")

# Expose money formatting to Jinja2
templates.env.globals["format_inr"] = format_inr
templates.env.globals["paise_to_decimal"] = paise_to_decimal


# Helper for optional user in web routes
def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    try:
        return get_current_user(request, get_token_from_request(request), db)
    except Exception:
        return None


# -------------------------------------------------------------------
# Landing & Auth
# -------------------------------------------------------------------
@router.get("/")
def root_redirect(user: User | None = Depends(get_optional_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse("/home", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/home", response_class=HTMLResponse)
def home_page(request: Request, user: User | None = Depends(get_optional_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request=request, name="home.html", context={
        "request": request,
        "user": user
    })


@router.get("/signup")
def signup_redirect():
    return RedirectResponse("/login?tab=signup", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str | None = None, success: str | None = None):
    return templates.TemplateResponse(request=request, name="auth/login.html", context={
        "request": request,
        "error": error,
        "success": success
    })


@router.post("/auth/login")
def login_form(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        user, token = authenticate_user(db, email, password)
        res = RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        res.set_cookie(
            key="access_token",
            value=f"Bearer {token}",
            max_age=12 * 3600,
            httponly=True,
            samesite="lax",
            secure=False
        )
        return res
    except Exception as e:
        detail = getattr(e, "detail", str(e))
        return RedirectResponse(f"/login?error={detail}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/auth/signup")
def signup_form(
    business_name: str = Form(...),
    owner_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    gstin: str | None = Form(None),
    db: Session = Depends(get_db)
):
    try:
        req = SignupRequest(
            business_name=business_name,
            owner_name=owner_name,
            email=email,
            password=password,
            gstin=gstin
        )
        biz, user, rec_code = signup_business(db, req)
        _, token = authenticate_user(db, email, password)
        res = RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        res.set_cookie(
            key="access_token",
            value=f"Bearer {token}",
            max_age=12 * 3600,
            httponly=True,
            samesite="lax",
            secure=False
        )
        return res
    except Exception as e:
        detail = getattr(e, "detail", str(e))
        return RedirectResponse(f"/login?error={detail}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/auth/forgot-password")
def forgot_password_form(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    email_clean = email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        return RedirectResponse(
            f"/login?tab=recover&error=No+account+found+with+email+{urllib.parse.quote(email_clean)}",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # Generate single-use secure reset token valid for 1 hour
    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    base_url = str(request.base_url).rstrip("/")
    reset_url = f"{base_url}/auth/reset-password?token={token}"

    # Send reset link to the same email id
    send_password_reset_email(user.email, reset_url)

    success_msg = f"A password reset link has been dispatched to {user.email}."
    return RedirectResponse(
        f"/login?tab=recover&success={urllib.parse.quote(success_msg)}&reset_url={urllib.parse.quote(reset_url)}",
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/auth/reset-password", response_class=HTMLResponse)
def reset_password_page(
    request: Request,
    token: str = Query(...),
    error: str | None = None,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.reset_token == token,
        User.reset_token_expires > datetime.utcnow()
    ).first()

    if not user:
        return RedirectResponse(
            "/login?tab=recover&error=This+password+reset+link+is+invalid+or+has+expired.+Please+request+a+new+one.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    return templates.TemplateResponse(
        request=request,
        name="auth/reset_password.html",
        context={
            "request": request,
            "token": token,
            "user_email": user.email,
            "error": error
        }
    )


@router.post("/auth/reset-password")
def reset_password_submit(
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    if new_password != confirm_password:
        return RedirectResponse(
            f"/auth/reset-password?token={token}&error=Passwords+do+not+match.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    if len(new_password) < 6:
        return RedirectResponse(
            f"/auth/reset-password?token={token}&error=Password+must+be+at+least+6+characters.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    user = db.query(User).filter(
        User.reset_token == token,
        User.reset_token_expires > datetime.utcnow()
    ).first()

    if not user:
        return RedirectResponse(
            "/login?tab=recover&error=This+password+reset+link+is+invalid+or+has+expired.+Please+request+a+new+one.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # Update password in company database
    user.password_hash = hash_password(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()

    # User immediately gets access to profile dashboard
    token_jwt = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "business_id": user.business_id,
        "user_name": user.name
    })

    res = RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    res.set_cookie(
        key="access_token",
        value=f"Bearer {token_jwt}",
        max_age=12 * 3600,
        httponly=True,
        samesite="lax",
        secure=False
    )
    return res


@router.post("/auth/recovery-reset")
def recovery_reset_form(
    email: str = Form(...),
    recovery_code: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        new_rec = reset_password_with_recovery_code(db, email, recovery_code, new_password)
        return RedirectResponse(
            f"/login?success=Password reset successful! Your new recovery code is {new_rec}",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        detail = getattr(e, "detail", str(e))
        return RedirectResponse(f"/login?error={detail}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/auth/logout")
def logout_form():
    res = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    res.delete_cookie("access_token")
    return res


# -------------------------------------------------------------------
# Authenticated Pages
# -------------------------------------------------------------------
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_view(
    request: Request,
    month: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    dash_data = get_dashboard_data(db, user.business_id, month=month)
    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "request": request,
        "user": user,
        "dash": dash_data,
        "selected_month": month,
        "active_page": "dashboard"
    })


@router.get("/upload", response_class=HTMLResponse)
def upload_view(
    request: Request,
    user: User = Depends(get_current_user)
):
    return templates.TemplateResponse(request=request, name="upload.html", context={
        "request": request,
        "user": user,
        "active_page": "upload"
    })


@router.get("/invoices", response_class=HTMLResponse)
def invoices_list_view(
    request: Request,
    view: str = "current",
    collection_id: int | None = None,
    direction: str | None = "all",
    status: str | None = "all",
    payment: str | None = "all",
    month: str | None = None,
    page: int = 1,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.collection import InvoiceCollection

    # 1. Fetch all saved collections for business
    cols_db = db.query(InvoiceCollection).filter(
        InvoiceCollection.business_id == user.business_id
    ).order_by(InvoiceCollection.created_at.desc()).all()

    collections_list = []
    month_names = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    for c in cols_db:
        total_paise = 0
        if c.invoice_ids:
            inv_totals = db.query(Invoice.total).filter(
                Invoice.id.in_(c.invoice_ids),
                Invoice.business_id == user.business_id,
                Invoice.deleted_at.is_(None)
            ).all()
            total_paise = sum(i[0] for i in inv_totals)

        m_name = month_names[c.month] if 1 <= c.month <= 12 else str(c.month)
        collections_list.append({
            "id": c.id,
            "name": c.name,
            "month": c.month,
            "year": c.year,
            "month_name": m_name,
            "invoice_count": len(c.invoice_ids),
            "total_paise": total_paise,
            "created_at": c.created_at
        })

    selected_collection = None
    if collection_id:
        selected_collection = next((c for c in collections_list if c["id"] == collection_id), None)
        if selected_collection:
            col_obj = next((c for c in cols_db if c.id == collection_id), None)
            if col_obj and col_obj.invoice_ids:
                invoices = db.query(Invoice).filter(
                    Invoice.id.in_(col_obj.invoice_ids),
                    Invoice.business_id == user.business_id,
                    Invoice.deleted_at.is_(None)
                ).order_by(Invoice.invoice_date.desc()).all()
                total = len(invoices)
            else:
                invoices = []
                total = 0
            view = "collections"
        else:
            invoices, total = list_invoices(db, user.business_id, in_workspace=True, page_size=100)
    else:
        invoices, total = list_invoices(
            db, user.business_id,
            direction=direction if direction != "all" else None,
            review_status=status if status != "all" else None,
            payment_status=payment if payment != "all" else None,
            month=month,
            in_workspace=True if view == "current" else None,
            page=page,
            page_size=100
        )

    return templates.TemplateResponse(request=request, name="invoices/list.html", context={
        "request": request,
        "user": user,
        "invoices": invoices,
        "total": total,
        "view": view,
        "collections": collections_list,
        "selected_collection": selected_collection,
        "filters": {"direction": direction, "status": status, "payment": payment, "month": month},
        "active_page": "invoices"
    })


@router.get("/invoices/new", response_class=HTMLResponse)
def new_invoice_view(
    request: Request,
    user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    customers = list_parties(db, user.business_id, party_type="customer")
    return templates.TemplateResponse(request=request, name="generator/new.html", context={
        "request": request,
        "user": user,
        "customers": customers,
        "today": date.today().strftime("%Y-%m-%d"),
        "active_page": "generator"
    })


@router.get("/invoices/{invoice_id}/review", response_class=HTMLResponse)
def review_invoice_view(
    invoice_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inv = get_invoice(db, user.business_id, invoice_id)
    return templates.TemplateResponse(request=request, name="invoices/review.html", context={
        "request": request,
        "user": user,
        "invoice": inv,
        "active_page": "invoices"
    })


@router.get("/parties", response_class=HTMLResponse)
def parties_view(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parties = list_parties(db, user.business_id)
    return templates.TemplateResponse(request=request, name="parties/list.html", context={
        "request": request,
        "user": user,
        "parties": parties,
        "active_page": "parties"
    })


@router.get("/parties/{party_id}/ledger", response_class=HTMLResponse)
def party_ledger_view(
    party_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ledger = get_party_ledger(db, user.business_id, party_id)
    return templates.TemplateResponse(request=request, name="parties/ledger.html", context={
        "request": request,
        "user": user,
        "ledger": ledger,
        "active_page": "parties"
    })


@router.get("/reports", response_class=HTMLResponse)
def reports_view(
    request: Request,
    month: str | None = None,
    user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    pnl = compute_profit_and_loss(db, user.business_id, month=month)
    ageing = compute_ageing_report(db, user.business_id, direction="sales")
    gstr3b = compute_gstr3b_summary(db, user.business_id, month=month)
    hsn = compute_hsn_summary(db, user.business_id, month=month)

    return templates.TemplateResponse(request=request, name="reports/index.html", context={
        "request": request,
        "user": user,
        "pnl": pnl,
        "ageing": ageing,
        "gstr3b": gstr3b,
        "hsn": hsn,
        "selected_month": month,
        "active_page": "reports"
    })


@router.get("/exports", response_class=HTMLResponse)
def exports_view(
    request: Request,
    user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    approved_invoices = (
        db.query(Invoice)
        .filter(
            Invoice.business_id == user.business_id,
            Invoice.review_status == "approved",
            Invoice.deleted_at.is_(None)
        )
        .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
        .all()
    )

    sales_count = sum(1 for i in approved_invoices if i.direction == "sales")
    purchase_count = sum(1 for i in approved_invoices if i.direction in ["purchase", "unknown"])
    total_exportable_value = sum(i.total for i in approved_invoices)
    total_taxable_value = sum(i.taxable for i in approved_invoices)
    total_gst_value = sum(i.cgst + i.sgst + i.igst for i in approved_invoices)

    return templates.TemplateResponse(request=request, name="exports/index.html", context={
        "request": request,
        "user": user,
        "active_page": "exports",
        "approved_invoices": approved_invoices,
        "total_approved": len(approved_invoices),
        "sales_count": sales_count,
        "purchase_count": purchase_count,
        "total_exportable_value": total_exportable_value,
        "total_taxable_value": total_taxable_value,
        "total_gst_value": total_gst_value
    })


@router.get("/alerts", response_class=HTMLResponse)
def alerts_view(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    alerts = (
        db.query(Alert)
        .filter(Alert.business_id == user.business_id)
        .order_by(Alert.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(request=request, name="alerts/list.html", context={
        "request": request,
        "user": user,
        "alerts": alerts,
        "active_page": "alerts"
    })


@router.get("/settings", response_class=HTMLResponse)
def settings_view(
    request: Request,
    user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db)
):
    biz = get_business_by_id(db, user.business_id)
    team = list_team_members(db, user)
    backups = db.query(Backup).order_by(Backup.created_at.desc()).all()

    return templates.TemplateResponse(request=request, name="settings/index.html", context={
        "request": request,
        "user": user,
        "business": biz,
        "team": team,
        "backups": backups,
        "active_page": "settings"
    })


# -------------------------------------------------------------------
# Public Share Page /s/{token}
# -------------------------------------------------------------------
@router.get("/s/{token}", response_class=HTMLResponse)
def public_share_view(
    token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    link = get_active_share_link(db, token)
    invoice = None
    title = f"Document #{link.ref}"

    if link.kind == "invoice":
        invoice = db.query(Invoice).filter(Invoice.id == int(link.ref)).first()
        if invoice:
            title = f"Invoice {invoice.invoice_no}"

    download_url = f"/s/{token}/pdf"

    return templates.TemplateResponse(request=request, name="share.html", context={
        "request": request,
        "title": title,
        "kind": link.kind,
        "ref": link.ref,
        "invoice": invoice,
        "download_url": download_url
    })


@router.get("/s/{token}/pdf")
def public_share_pdf_download(
    token: str,
    db: Session = Depends(get_db)
):
    link = get_active_share_link(db, token)
    if link.kind == "invoice":
        pdf_bytes = generate_sales_invoice_pdf(db, link.business_id, int(link.ref))
        filename = f"Invoice_{link.ref}.pdf"
    else:
        pdf_bytes = generate_monthly_report_pdf(db, link.business_id, link.ref)
        filename = f"Monthly_Report_{link.ref}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )
