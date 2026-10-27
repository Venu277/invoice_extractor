import secrets
import smtplib
import urllib.parse
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import settings
from app.models.share import ShareLink
from app.models.invoice import Invoice
from app.services.money import format_inr


def create_share_link(
    db: Session,
    business_id: int,
    kind: str,  # invoice or report
    ref: str    # invoice_id or month YYYY-MM
) -> ShareLink:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=30)

    link = ShareLink(
        business_id=business_id,
        kind=kind,
        ref=str(ref),
        token=token,
        expires_at=expires_at,
        revoked=False
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def get_active_share_link(db: Session, token: str) -> ShareLink:
    link = db.query(ShareLink).filter(
        ShareLink.token == token,
        ShareLink.revoked.is_(False)
    ).first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared link is invalid or has been revoked."
        )
    if datetime.utcnow() > link.expires_at:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Shared link has expired."
        )
    return link


def revoke_share_link(db: Session, business_id: int, token: str) -> None:
    link = db.query(ShareLink).filter(
        ShareLink.token == token,
        ShareLink.business_id == business_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found.")
    link.revoked = True
    db.commit()


def build_whatsapp_url(share_url: str, title: str, amount_str: str) -> str:
    msg = f"Hello, please view your {title} for {amount_str} here: {share_url}"
    encoded = urllib.parse.quote(msg)
    return f"https://wa.me/?text={encoded}"


def send_email_share(
    to_email: str,
    subject: str,
    share_url: str,
    body_intro: str
) -> tuple[bool, str]:
    """Sends share link via SMTP if configured; degrades with clear message when not."""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        return False, "Email service is not configured. Please set SMTP credentials in settings or .env."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = to_email

        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <p>{body_intro}</p>
            <p style="margin: 20px 0;">
              <a href="{share_url}" style="background-color: #1F3A5F; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">
                View Document
              </a>
            </p>
            <p style="font-size: 12px; color: #777;">This secure link is valid for 30 days.</p>
          </body>
        </html>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        return True, "Email sent successfully."
    except Exception as e:
        return False, f"Failed to send email: {e}"


def send_password_reset_email(to_email: str, reset_url: str) -> tuple[bool, str]:
    """Sends password assignment link via SMTP if configured."""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        return False, "Email service is not configured. (Using direct test link in development mode)."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Assign New Password | Axion"
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = to_email

        html = f"""
        <html>
          <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #19371c; background-color: #effdee; padding: 24px;">
            <div style="max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 32px; border: 1px solid #c6edc3;">
              <h2 style="font-size: 20px; font-weight: 600; color: #19371c; margin-top: 0;">Password Reset Request</h2>
              <p style="font-size: 14px; color: #435445;">You requested a link to assign a new password for your Axion account.</p>
              <p style="margin: 28px 0;">
                <a href="{reset_url}" style="background-color: #90cf8e; color: #19371c; font-weight: 600; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block;">
                  Assign New Password
                </a>
              </p>
              <p style="font-size: 12px; color: #768a78; line-height: 1.5;">If the button above does not work, copy and paste this link into your browser:<br><a href="{reset_url}" style="color: #19371c;">{reset_url}</a></p>
              <p style="font-size: 12px; color: #768a78;">This link is single-use and will expire in 1 hour. If you did not make this request, your account remains secure and no action is required.</p>
            </div>
          </body>
        </html>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        return True, "Email sent successfully."
    except Exception as e:
        return False, f"Failed to send email: {e}"
