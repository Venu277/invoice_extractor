from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.models.invoice import Invoice
from app.schemas.generator import ShareLinkResponse
from app.services.share_service import (
    create_share_link,
    get_active_share_link,
    revoke_share_link,
    build_whatsapp_url,
    send_email_share
)
from app.services.money import format_inr

router = APIRouter(prefix="/shares", tags=["Sharing"])


@router.post("", response_model=ShareLinkResponse, status_code=status.HTTP_201_CREATED)
def share_document(
    kind: str,  # invoice or report
    ref: str,   # invoice_id or month
    request: Request,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    link = create_share_link(db, current_user.business_id, kind, ref)
    base_url = str(request.base_url).rstrip("/")
    share_url = f"{base_url}/s/{link.token}"

    title = f"Invoice #{ref}" if kind == "invoice" else f"Monthly Report ({ref})"
    amt_str = ""
    if kind == "invoice":
        inv = db.query(Invoice).filter(Invoice.id == int(ref), Invoice.business_id == current_user.business_id).first()
        if inv:
            amt_str = format_inr(inv.total)

    wa_url = build_whatsapp_url(share_url, title, amt_str)

    return ShareLinkResponse(
        id=link.id,
        kind=link.kind,
        ref=link.ref,
        token=link.token,
        share_url=share_url,
        whatsapp_url=wa_url,
        expires_at=link.expires_at.isoformat(),
        revoked=link.revoked
    )


@router.delete("/{token}", status_code=status.HTTP_204_NO_CONTENT)
def revoke(
    token: str,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    revoke_share_link(db, current_user.business_id, token)
    return None
