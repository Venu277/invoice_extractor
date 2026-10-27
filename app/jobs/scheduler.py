import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.jobs.jobs import (
    job_due_and_overdue_alerts,
    job_recurring_invoices,
    job_nightly_backup,
    job_cleanup_expired_links
)

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def start_scheduler():
    if not scheduler.running:
        # 1. Due alerts: run daily at 08:00 AM (and every 6 hours)
        scheduler.add_job(
            job_due_and_overdue_alerts,
            IntervalTrigger(hours=6),
            id="job_due_and_overdue_alerts",
            replace_existing=True
        )

        # 2. Recurring invoices: run daily at 00:05 AM
        scheduler.add_job(
            job_recurring_invoices,
            CronTrigger(hour=0, minute=5),
            id="job_recurring_invoices",
            replace_existing=True
        )

        # 3. Nightly backup: run daily at 02:00 AM
        scheduler.add_job(
            job_nightly_backup,
            CronTrigger(hour=2, minute=0),
            id="job_nightly_backup",
            replace_existing=True
        )

        # 4. Cleanup expired share links: run every 12 hours
        scheduler.add_job(
            job_cleanup_expired_links,
            IntervalTrigger(hours=12),
            id="job_cleanup_expired_links",
            replace_existing=True
        )

        scheduler.start()
        logger.info("InvoiceIQ background job scheduler started.")


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("InvoiceIQ background job scheduler shut down.")
