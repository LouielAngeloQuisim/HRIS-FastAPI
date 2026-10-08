"""Durable, opt-in payslip outbox worker.

An SMTP exception after a send attempt is ambiguous; those jobs move to
``uncertain`` and are never automatically retried. Only definite connection
setup failures receive bounded retries. The worker logs opaque job IDs only.
"""

from __future__ import annotations

import argparse
import html
import logging
import smtplib
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

from emails.message import Message
from reportlab.lib.pagesizes import letter  # type: ignore[import-untyped]
from reportlab.pdfgen import canvas  # type: ignore[import-untyped]
from sqlmodel import Session, col, select

from app.config.database import engine
from app.config.settings import settings
from app.payroll.models import PayrollDeliveryOutbox

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5
LEASE = timedelta(minutes=10)
POLL_SECONDS = 15


def _money(value: object) -> str:
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            return "Unavailable"
        return f"PHP {amount:,.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return "Unavailable"


def render_payslip_pdf(snapshot: dict[str, Any]) -> bytes:
    """Render a compact PDF exclusively from the immutable outbox snapshot."""
    entry = snapshot.get("entry", {})
    amounts = entry.get("amounts", {})
    employee = entry.get("employee", {})
    run = snapshot.get("run", {})
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter, pageCompression=1)
    pdf.setTitle("Employee payslip")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(48, 744, "Employee Payslip")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(48, 720, f"Employee: {str(employee.get('name', 'Employee'))[:100]}")
    pdf.drawString(48, 704, f"Employee code: {str(employee.get('code', ''))[:64]}")
    period = run.get("period", {})
    pdf.drawString(
        48, 688, f"Earning period: {period.get('from', '')} to {period.get('to', '')}"
    )
    pdf.drawString(48, 672, f"Payment date: {run.get('payment_date', '')}")
    pdf.line(48, 658, 564, 658)
    y = 638
    for label, amount in (("Gross earnings", amounts.get("gross")),):
        pdf.drawString(48, y, label)
        pdf.drawRightString(564, y, _money(amount))
        y -= 22
    for heading, key in (
        ("Earnings breakdown", "earnings"),
        ("Deduction breakdown", "deduction_lines"),
    ):
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(48, y, heading)
        y -= 16
        pdf.setFont("Helvetica", 9)
        lines = amounts.get(key, {})
        if isinstance(lines, dict):
            for label, amount in sorted(lines.items()):
                if y < 90:
                    pdf.showPage()
                    pdf.setFont("Helvetica", 9)
                    y = 744
                pdf.drawString(56, y, str(label).replace("_", " ")[:72])
                pdf.drawRightString(564, y, _money(amount))
                y -= 14
        y -= 6
    for label, amount in (
        ("Total deductions", amounts.get("deductions")),
        ("Net pay", amounts.get("net")),
    ):
        pdf.setFont("Helvetica-Bold", 10 if label == "Net pay" else 9)
        pdf.drawString(48, y, label)
        pdf.drawRightString(564, y, _money(amount))
        y -= 22
    pdf.line(48, y + 10, 564, y + 10)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(
        48, 54, "This payslip is not evidence of a bank transfer or payment."
    )
    pdf.save()
    return output.getvalue()


def _claim_due_jobs(*, now: datetime | None = None, limit: int = 25) -> list[uuid.UUID]:
    current = now or datetime.now(timezone.utc)
    with Session(engine) as session:
        expired = session.exec(
            select(PayrollDeliveryOutbox)
            .where(
                PayrollDeliveryOutbox.status == "processing",
                col(PayrollDeliveryOutbox.claimed_until) < current,
            )
            .with_for_update(skip_locked=True)
            .limit(limit)
        ).all()
        for job in expired:
            job.status = "uncertain"
            job.claimed_until = None
            job.last_error_code = "worker_lease_expired_after_send_started"
            session.add(job)
        if expired:
            session.flush()

        due = session.exec(
            select(PayrollDeliveryOutbox)
            .where(
                col(PayrollDeliveryOutbox.status).in_(["scheduled", "failed"]),
                col(PayrollDeliveryOutbox.next_attempt_at) <= current,
                PayrollDeliveryOutbox.attempts < MAX_ATTEMPTS,
                col(PayrollDeliveryOutbox.recipient_snapshot).is_not(None),
            )
            .order_by(
                col(PayrollDeliveryOutbox.next_attempt_at),
                col(PayrollDeliveryOutbox.created_at),
            )
            .with_for_update(skip_locked=True)
            .limit(limit)
        ).all()
        for job in due:
            job.status = "processing"
            job.claimed_until = current + LEASE
            job.attempts += 1
            job.updated_at = current
            session.add(job)
        due_ids = [job.id for job in due]
        session.commit()
        return due_ids


def _render_email(snapshot: dict[str, Any]) -> tuple[str, str]:
    entry = snapshot.get("entry", {})
    employee = entry.get("employee", {})
    name = html.escape(str(employee.get("name", "Employee")))
    period = snapshot.get("run", {}).get("period", {})
    subject = f"Payroll payslip: {period.get('from', '')} to {period.get('to', '')}"
    return (
        subject,
        f"<p>Hello {name},</p><p>Your payslip for {html.escape(str(period.get('from', '')))} to {html.escape(str(period.get('to', '')))} is attached.</p><p>This document is not evidence of a bank transfer or payment.</p>",
    )


def _send_smtp_once(
    *,
    message: Message,
    recipient: str,
    sender: str,
    host: str,
    port: int,
    use_tls: bool,
    use_ssl: bool,
    username: str | None,
    password: str | None,
) -> None:
    """Submit one SMTP transaction without library-level disconnect retries.

    The ``emails`` SMTP backend retries ``SMTPServerDisconnected`` once. A
    disconnect after DATA may mean the server accepted the message, so that
    retry can send a payslip twice. Use smtplib directly and submit DATA once;
    the caller records any ambiguous result as ``uncertain`` for reconciliation.
    """
    message.set_mail_to(recipient)
    smtp_type = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    smtp = smtp_type(host, port, timeout=10)
    try:
        if use_tls:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
        if username:
            smtp.login(username, password or "")
        refused = smtp.sendmail(
            sender, recipient, message.as_bytes()
        )
        if refused:
            raise RuntimeError("smtp_recipient_rejected")
    finally:
        try:
            smtp.quit()
        except Exception:
            # A failure during QUIT happens after sendmail has either returned
            # SMTP acceptance or raised an ambiguous DATA outcome. Preserve
            # that result instead of converting a confirmed send into a retry.
            smtp.close()


def _send_job(job_id: uuid.UUID) -> None:
    smtp_host = settings.SMTP_HOST
    sender = settings.EMAILS_FROM_EMAIL
    with Session(engine) as session:
        job = session.exec(
            select(PayrollDeliveryOutbox)
            .where(
                PayrollDeliveryOutbox.id == job_id,
                PayrollDeliveryOutbox.status == "processing",
            )
            .with_for_update()
        ).first()
        if job is None:
            return
        if not settings.emails_enabled or not smtp_host or not sender or not job.recipient_snapshot:
            job.status = "blocked_email"
            job.last_error_code = (
                "email_transport_not_configured"
                if job.recipient_snapshot
                else "recipient_missing"
            )
            job.claimed_until = None
            session.add(job)
            session.commit()
            return
        snapshot = dict(job.content_snapshot)
        recipient = job.recipient_snapshot
        attempts = job.attempts
        # Keep the job leased while rendering and submitting; do not hold a DB
        # lock across the SMTP call.
        session.commit()

    subject, body = _render_email(snapshot)
    pdf_bytes = render_payslip_pdf(snapshot)
    message = Message(
        subject=subject,
        html=body,
        mail_from=(
            settings.EMAILS_FROM_NAME or settings.PROJECT_NAME,
            str(settings.EMAILS_FROM_EMAIL),
        ),
        attachments=[
            {
                "filename": "payslip.pdf",
                "mime_type": "application/pdf",
                "data": pdf_bytes,
            }
        ],
    )
    try:
        _send_smtp_once(
            message=message,
            recipient=recipient,
            sender=sender,
            host=smtp_host,
            port=settings.SMTP_PORT,
            use_tls=settings.SMTP_TLS,
            use_ssl=settings.SMTP_SSL,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
        )
    except smtplib.SMTPRecipientsRefused:
        # SMTP rejected the recipient before DATA, so delivery definitely did
        # not occur. Mark it blocked for address correction instead of asking
        # an operator to resolve a false ambiguous-send warning.
        with Session(engine) as session:
            job = session.exec(
                select(PayrollDeliveryOutbox)
                .where(PayrollDeliveryOutbox.id == job_id)
                .with_for_update()
            ).first()
            if job is not None and job.status == "processing":
                job.status = "blocked_email"
                job.last_error_code = "smtp_recipient_rejected"
                job.claimed_until = None
                session.add(job)
                session.commit()
        logger.warning("Payslip recipient was rejected for job %s", job_id)
        return
    except (ConnectionRefusedError, socket.gaierror) as exc:
        # These errors happen before SMTP can accept a message. Retry with
        # exponential backoff, bounded to five attempts.
        with Session(engine) as session:
            job = session.exec(
                select(PayrollDeliveryOutbox)
                .where(PayrollDeliveryOutbox.id == job_id)
                .with_for_update()
            ).first()
            if job is not None and job.status == "processing":
                job.status = "failed"
                job.last_error_code = type(exc).__name__
                job.claimed_until = None
                job.next_attempt_at = datetime.now(timezone.utc) + timedelta(
                    minutes=min(60, 2**attempts)
                )
                session.add(job)
                session.commit()
        logger.warning("Payslip delivery connection failed for job %s", job_id)
        return
    except Exception as exc:
        # SMTP may have accepted the DATA before the client lost its response.
        # Retrying automatically could send the same payslip twice.
        with Session(engine) as session:
            job = session.exec(
                select(PayrollDeliveryOutbox)
                .where(PayrollDeliveryOutbox.id == job_id)
                .with_for_update()
            ).first()
            if job is not None and job.status == "processing":
                job.status = "uncertain"
                job.last_error_code = type(exc).__name__[:64]
                job.claimed_until = None
                session.add(job)
                session.commit()
        logger.warning("Payslip delivery outcome is uncertain for job %s", job_id)
        return

    with Session(engine) as session:
        job = session.exec(
            select(PayrollDeliveryOutbox)
            .where(PayrollDeliveryOutbox.id == job_id)
            .with_for_update()
        ).first()
        if job is not None and job.status == "processing":
            job.status = "sent"
            job.sent_at = datetime.now(timezone.utc)
            job.claimed_until = None
            job.last_error_code = None
            session.add(job)
            session.commit()
    logger.info("Payslip delivery sent for job %s", job_id)


def run_worker(*, once: bool = False) -> None:
    if not settings.PAYSLIP_DELIVERY_ENABLED:
        logger.info("Payslip delivery worker is disabled; remaining idle")
        if once:
            return
        # Keep the supervised production process inert while delivery is off.
        # Operators must recreate the container after changing its environment.
        while True:
            time.sleep(POLL_SECONDS)
    while True:
        jobs = _claim_due_jobs()
        for job_id in jobs:
            _send_job(job_id)
        if once:
            return
        time.sleep(POLL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once", action="store_true", help="Process one due batch and exit"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run_worker(once=args.once)


if __name__ == "__main__":
    main()
