import logging
from datetime import datetime
from app.db import SessionLocal
from app.models.business import Business
from app.models.share import ShareLink
from app.services.alerts_service import check_and_create_due_alerts, check_gst_deadline_alerts
from app.services.recurring_service import process_due_recurring_invoices
from app.services.backup_service import create_backup

logger = logging.getLogger(__name__)


def job_due_and_overdue_alerts():
    """Daily check for due soon & overdue alerts across all businesses."""
    db = SessionLocal()
    try:
        businesses = db.query(Business).all()
        for b in businesses:
            check_and_create_due_alerts(db, b.id)
            check_gst_deadline_alerts(db, b.id)
        logger.info("Due & overdue alerts job completed successfully.")
    except Exception as e:
        logger.error(f"Error in job_due_and_overdue_alerts: {e}", exc_info=True)
    finally:
        db.close()


def job_recurring_invoices():
    """Daily generation of due recurring invoices."""
    db = SessionLocal()
    try:
        invoices = process_due_recurring_invoices(db)
        logger.info(f"Recurring invoices job completed. Created {len(invoices)} invoice(s).")
    except Exception as e:
        logger.error(f"Error in job_recurring_invoices: {e}", exc_info=True)
    finally:
        db.close()


def job_nightly_backup():
    """Nightly automated database and uploads backup (SQLite only)."""
    from app.config import settings
    if not settings.DATABASE_URL.startswith("sqlite"):
        logger.info("Nightly backup skipped: Automated provider backups are active on PostgreSQL.")
        return

    db = SessionLocal()
    try:
        backup = create_backup(db, kind="scheduled")
        logger.info(f"Nightly backup created: {backup.path}")
    except Exception as e:
        logger.error(f"Error in job_nightly_backup: {e}", exc_info=True)
    finally:
        db.close()


def job_cleanup_expired_links():
    """Revokes/cleans up expired share links."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        expired = db.query(ShareLink).filter(
            ShareLink.expires_at < now,
            ShareLink.revoked.is_(False)
        ).all()
        for link in expired:
            link.revoked = True
        db.commit()
        logger.info(f"Cleaned up {len(expired)} expired share link(s).")
    except Exception as e:
        logger.error(f"Error in job_cleanup_expired_links: {e}", exc_info=True)
    finally:
        db.close()
