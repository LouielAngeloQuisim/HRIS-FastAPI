"""Payslip worker renders frozen snapshots and treats uncertain SMTP safely."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from emails.message import Message
from sqlalchemy import delete
from sqlmodel import Session

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.delivery_worker import (
    MAX_ATTEMPTS,
    _claim_due_jobs,
    _money,
    _send_job,
    render_payslip_pdf,
    run_worker,
)
from app.payroll.models import PayrollDeliveryOutbox, PayrollEntry, PayrollRun


def _snapshot() -> dict:
    return {
        "run": {
            "period": {"from": "2026-09-01", "to": "2026-09-30"},
            "payment_date": "2026-10-05",
        },
        "entry": {
            "employee": {"name": "QA Employee", "code": "QA0001"},
            "amounts": {
                "gross": "1000.00",
                "deductions": "100.00",
                "net": "900.00",
                "earnings": {"regular": "1000.00"},
                "deduction_lines": {"tax": "100.00"},
            },
        },
    }


def test_payslip_pdf_is_rendered_from_the_snapshot() -> None:
    pdf = render_payslip_pdf(_snapshot())
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 500


def test_payslip_currency_formatting_uses_decimal_half_even_rounding() -> None:
    assert _money("1.005") == "PHP 1.00"
    assert _money("1.015") == "PHP 1.02"
    assert _money("invalid") == "Unavailable"
    assert _money("NaN") == "Unavailable"


def _delivery_job(db: Session) -> PayrollDeliveryOutbox:
    employee = EmployeeRecords(
        employee_code=f"MAIL-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Employee",
        birthdate="1990-01-01",
        email="qa@example.test",
    )
    db.add(employee)
    db.flush()
    run = PayrollRun(
        date_from=date(2026, 9, 1), date_to=date(2026, 9, 30), created_by=None
    )
    db.add(run)
    db.flush()
    entry = PayrollEntry(
        payroll_run_id=run.id,
        employee_id=employee.id,
        basic_rate=Decimal("1000"),
        rate_date_from=date(2026, 9, 1),
        rate_date_to=date(2026, 9, 30),
        gross_pay=Decimal("1000"),
        total_deductions=Decimal("100"),
        net_pay=Decimal("900"),
        taxable_income=Decimal("1000"),
    )
    db.add(entry)
    db.flush()
    job = PayrollDeliveryOutbox(
        payroll_entry_id=entry.id,
        recipient_snapshot=employee.email,
        content_snapshot=_snapshot(),
        status="processing",
        attempts=1,
        claimed_until=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@pytest.fixture
def delivery_job(db: Session):
    job = _delivery_job(db)
    yield job
    entry = db.get(PayrollEntry, job.payroll_entry_id)
    run_id = entry.payroll_run_id if entry else None
    employee_id = entry.employee_id if entry else None
    db.exec(delete(PayrollDeliveryOutbox).where(PayrollDeliveryOutbox.id == job.id))
    db.exec(delete(PayrollEntry).where(PayrollEntry.id == job.payroll_entry_id))
    if run_id:
        db.exec(delete(PayrollRun).where(PayrollRun.id == run_id))
    if employee_id:
        db.exec(delete(EmployeeRecords).where(EmployeeRecords.id == employee_id))
    db.commit()


def test_delivery_attaches_pdf_and_marks_success(
    db: Session, monkeypatch, delivery_job: PayrollDeliveryOutbox
) -> None:
    monkeypatch.setattr(settings, "SMTP_HOST", "mailcatcher")
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "noreply@example.test")
    job = delivery_job
    with patch.object(Message, "send", autospec=True, return_value=None) as send:
        _send_job(job.id)
    db.refresh(job)
    message = send.call_args.args[0]
    assert job.status == "sent"
    assert job.sent_at is not None
    assert message.attachments
    attachment = next(iter(message.attachments))
    assert attachment.mime_type == "application/pdf"


def test_ambiguous_smtp_failure_is_not_retried(
    db: Session, monkeypatch, delivery_job: PayrollDeliveryOutbox
) -> None:
    monkeypatch.setattr(settings, "SMTP_HOST", "mailcatcher")
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "noreply@example.test")
    job = delivery_job
    with patch.object(Message, "send", autospec=True, side_effect=TimeoutError()):
        _send_job(job.id)
    db.refresh(job)
    assert job.status == "uncertain"
    assert job.last_error_code == "TimeoutError"


def test_due_job_is_claimed_once_and_attempt_count_is_incremented(
    db: Session, delivery_job: PayrollDeliveryOutbox
) -> None:
    job = delivery_job
    now = datetime.now(timezone.utc)
    job.status = "scheduled"
    job.attempts = 0
    job.next_attempt_at = now - timedelta(seconds=1)
    job.claimed_until = None
    db.add(job)
    db.commit()

    claimed = _claim_due_jobs(now=now)

    db.refresh(job)
    assert claimed == [job.id]
    assert job.status == "processing"
    assert job.attempts == 1
    assert job.claimed_until is not None and job.claimed_until > now


def test_expired_send_lease_becomes_uncertain_and_is_not_reclaimed(
    db: Session, delivery_job: PayrollDeliveryOutbox
) -> None:
    job = delivery_job
    now = datetime.now(timezone.utc)
    job.status = "processing"
    job.claimed_until = now - timedelta(seconds=1)
    db.add(job)
    db.commit()

    claimed = _claim_due_jobs(now=now)

    db.refresh(job)
    assert job.id not in claimed
    assert job.status == "uncertain"
    assert job.claimed_until is None
    assert job.last_error_code == "worker_lease_expired_after_send_started"


def test_retry_limit_excludes_exhausted_job(
    db: Session, delivery_job: PayrollDeliveryOutbox
) -> None:
    job = delivery_job
    job.status = "failed"
    job.attempts = MAX_ATTEMPTS
    job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    job.claimed_until = None
    db.add(job)
    db.commit()

    assert _claim_due_jobs() == []
    db.refresh(job)
    assert job.status == "failed"
    assert job.attempts == MAX_ATTEMPTS


def test_disabled_worker_never_claims_or_sends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.payroll.delivery_worker as worker

    monkeypatch.setattr(settings, "PAYSLIP_DELIVERY_ENABLED", False)
    monkeypatch.setattr(
        worker, "_claim_due_jobs", lambda: pytest.fail("claimed while disabled")
    )

    run_worker(once=True)
