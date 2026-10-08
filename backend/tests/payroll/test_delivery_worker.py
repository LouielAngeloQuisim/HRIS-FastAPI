"""Payslip worker renders frozen snapshots and treats uncertain SMTP safely."""

import os
import socketserver
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch

import pytest
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
    with patch("app.payroll.delivery_worker._send_smtp_once") as send:
        _send_job(job.id)
    db.refresh(job)
    message = send.call_args.kwargs["message"]
    assert job.status == "sent"
    assert job.sent_at is not None
    assert message.attachments
    attachment = next(iter(message.attachments))
    assert attachment.mime_type == "application/pdf"


class _SMTPCollector(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self) -> None:
        self.messages: list[bytes] = []
        collector = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                self.wfile.write(b"220 local test sink\r\n")
                while line := self.rfile.readline():
                    command = line.decode("ascii", errors="replace").strip().split(" ", 1)[0].upper()
                    if command in {"EHLO", "HELO"}:
                        self.wfile.write(b"250-local test sink\r\n250 SIZE 10485760\r\n")
                    elif command == "DATA":
                        self.wfile.write(b"354 send message data\r\n")
                        chunks: list[bytes] = []
                        while data_line := self.rfile.readline():
                            if data_line == b".\r\n":
                                break
                            chunks.append(data_line[1:] if data_line.startswith(b"..") else data_line)
                        collector.messages.append(b"".join(chunks))
                        self.wfile.write(b"250 accepted by local test sink\r\n")
                    elif command == "QUIT":
                        self.wfile.write(b"221 closing connection\r\n")
                        return
                    else:
                        self.wfile.write(b"250 ok\r\n")

        super().__init__(("127.0.0.1", 0), Handler)


class _SMTPAcceptThenDisconnect(socketserver.ThreadingTCPServer):
    """Accept DATA, then drop the connection before SMTP confirms acceptance."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self) -> None:
        self.messages: list[bytes] = []
        collector = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                self.wfile.write(b"220 local test sink\r\n")
                while line := self.rfile.readline():
                    command = line.decode("ascii", errors="replace").strip().split(" ", 1)[0].upper()
                    if command in {"EHLO", "HELO"}:
                        self.wfile.write(b"250-local test sink\r\n250 SIZE 10485760\r\n")
                    elif command == "DATA":
                        self.wfile.write(b"354 send message data\r\n")
                        chunks: list[bytes] = []
                        while data_line := self.rfile.readline():
                            if data_line == b".\r\n":
                                break
                            chunks.append(data_line[1:] if data_line.startswith(b"..") else data_line)
                        collector.messages.append(b"".join(chunks))
                        # The server accepted and recorded the message, but the
                        # client never receives the final 250 response.
                        return
                    elif command == "QUIT":
                        self.wfile.write(b"221 closing connection\r\n")
                        return
                    else:
                        self.wfile.write(b"250 ok\r\n")

        super().__init__(("127.0.0.1", 0), Handler)


class _SMTPRejectRecipient(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self) -> None:
        self.recipient_attempts = 0
        sink = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                self.wfile.write(b"220 local test sink\r\n")
                while line := self.rfile.readline():
                    command = line.decode("ascii", errors="replace").strip().split(" ", 1)[0].upper()
                    if command in {"EHLO", "HELO"}:
                        self.wfile.write(b"250-local test sink\r\n250 SIZE 10485760\r\n")
                    elif command == "RCPT":
                        sink.recipient_attempts += 1
                        self.wfile.write(b"550 recipient rejected\r\n")
                    elif command == "QUIT":
                        self.wfile.write(b"221 closing connection\r\n")
                        return
                    else:
                        self.wfile.write(b"250 ok\r\n")

        super().__init__(("127.0.0.1", 0), Handler)


def test_worker_claims_scheduled_job_and_sends_frozen_pdf_to_local_smtp_sink(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    delivery_job: PayrollDeliveryOutbox,
) -> None:
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "noreply@example.test")
    monkeypatch.setattr(settings, "PAYSLIP_DELIVERY_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_TLS", False)
    monkeypatch.setattr(settings, "SMTP_SSL", False)
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    with _SMTPCollector() as sink:
        monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
        monkeypatch.setattr(settings, "SMTP_PORT", sink.server_address[1])
        worker_thread = threading.Thread(target=sink.serve_forever, daemon=True)
        worker_thread.start()
        delivery_job.status = "scheduled"
        delivery_job.attempts = 0
        delivery_job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        delivery_job.claimed_until = None
        db.add(delivery_job)
        db.commit()
        try:
            run_worker(once=True)
        finally:
            sink.shutdown()
            worker_thread.join(timeout=2)

    db.refresh(delivery_job)
    assert delivery_job.status == "sent", delivery_job.last_error_code
    assert len(sink.messages) == 1
    message = BytesParser(policy=policy.default).parsebytes(sink.messages[0])
    assert message["To"] == "qa@example.test"
    assert "2026-09-01 to 2026-09-30" in str(message["Subject"])
    attachment = next(part for part in message.iter_attachments())
    assert attachment.get_filename() == "payslip.pdf"
    assert attachment.get_content_type() == "application/pdf"
    assert attachment.get_payload(decode=True).startswith(b"%PDF-")


def test_smtp_accept_then_disconnect_marks_uncertain_without_automatic_resend(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    delivery_job: PayrollDeliveryOutbox,
) -> None:
    monkeypatch.setattr(settings, "PAYSLIP_DELIVERY_ENABLED", True)
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "noreply@example.test")
    monkeypatch.setattr(settings, "SMTP_TLS", False)
    monkeypatch.setattr(settings, "SMTP_SSL", False)
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    with _SMTPAcceptThenDisconnect() as sink:
        monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
        monkeypatch.setattr(settings, "SMTP_PORT", sink.server_address[1])
        server_thread = threading.Thread(target=sink.serve_forever, daemon=True)
        server_thread.start()
        delivery_job.status = "scheduled"
        delivery_job.attempts = 0
        delivery_job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        delivery_job.claimed_until = None
        db.add(delivery_job)
        db.commit()
        try:
            run_worker(once=True)
            run_worker(once=True)
        finally:
            sink.shutdown()
            server_thread.join(timeout=2)

    db.refresh(delivery_job)
    assert len(sink.messages) == 1
    assert delivery_job.status == "uncertain"
    assert delivery_job.last_error_code == "SMTPServerDisconnected"
    assert delivery_job.attempts == 1


def test_smtp_recipient_rejection_is_blocked_for_correction_not_uncertain(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    delivery_job: PayrollDeliveryOutbox,
) -> None:
    monkeypatch.setattr(settings, "PAYSLIP_DELIVERY_ENABLED", True)
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "noreply@example.test")
    monkeypatch.setattr(settings, "SMTP_TLS", False)
    monkeypatch.setattr(settings, "SMTP_SSL", False)
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    with _SMTPRejectRecipient() as sink:
        monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
        monkeypatch.setattr(settings, "SMTP_PORT", sink.server_address[1])
        server_thread = threading.Thread(target=sink.serve_forever, daemon=True)
        server_thread.start()
        delivery_job.status = "scheduled"
        delivery_job.attempts = 0
        delivery_job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        delivery_job.claimed_until = None
        db.add(delivery_job)
        db.commit()
        try:
            run_worker(once=True)
            run_worker(once=True)
        finally:
            sink.shutdown()
            server_thread.join(timeout=2)

    db.refresh(delivery_job)
    assert sink.recipient_attempts == 1
    assert delivery_job.status == "blocked_email"
    assert delivery_job.last_error_code == "smtp_recipient_rejected"
    assert delivery_job.attempts == 1


def test_ambiguous_smtp_failure_is_not_retried(
    db: Session, monkeypatch, delivery_job: PayrollDeliveryOutbox
) -> None:
    monkeypatch.setattr(settings, "SMTP_HOST", "mailcatcher")
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "noreply@example.test")
    job = delivery_job
    with patch(
        "app.payroll.delivery_worker._send_smtp_once", side_effect=TimeoutError()
    ):
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


def test_worker_restart_does_not_resend_job_with_expired_send_lease(
    db: Session,
    delivery_job: PayrollDeliveryOutbox,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A restarted process reconciles an interrupted send as uncertain, not due."""
    import app.payroll.delivery_worker as worker

    job = delivery_job
    job.status = "processing"
    job.attempts = 1
    job.claimed_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.add(job)
    db.commit()

    monkeypatch.setattr(settings, "PAYSLIP_DELIVERY_ENABLED", True)
    monkeypatch.setattr(worker, "HEARTBEAT_FILE", tmp_path / "heartbeat")
    sent_ids: list[uuid.UUID] = []
    monkeypatch.setattr(worker, "_send_job", sent_ids.append)

    # This is the restarted worker's first poll. The prior process may have
    # submitted SMTP DATA before dying, so automatic redelivery is forbidden.
    run_worker(once=True)

    db.refresh(job)
    assert sent_ids == []
    assert job.status == "uncertain"
    assert job.attempts == 1
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


def test_connection_failures_retry_within_the_bounded_attempt_limit(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    delivery_job: PayrollDeliveryOutbox,
) -> None:
    monkeypatch.setattr(settings, "SMTP_HOST", "mail.example.test")
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "noreply@example.test")
    job = delivery_job
    job.status = "processing"
    job.attempts = 1
    db.add(job)
    db.commit()

    with patch(
        "app.payroll.delivery_worker._send_smtp_once",
        side_effect=ConnectionRefusedError(),
    ) as send:
        _send_job(job.id)
        db.refresh(job)
        assert job.status == "failed"
        assert job.attempts == 1
        assert job.last_error_code == "ConnectionRefusedError"

        for expected_attempt in range(2, MAX_ATTEMPTS + 1):
            now = datetime.now(timezone.utc)
            job.next_attempt_at = now - timedelta(seconds=1)
            db.add(job)
            db.commit()

            assert _claim_due_jobs(now=now) == [job.id]
            db.refresh(job)
            assert job.status == "processing"
            assert job.attempts == expected_attempt

            _send_job(job.id)
            db.refresh(job)
            assert job.status == "failed"
            assert job.next_attempt_at is not None
            assert job.next_attempt_at > now

        assert send.call_count == MAX_ATTEMPTS

    now = datetime.now(timezone.utc)
    job.next_attempt_at = now - timedelta(seconds=1)
    db.add(job)
    db.commit()
    assert _claim_due_jobs(now=now) == []
    db.refresh(job)
    assert job.status == "failed"
    assert job.attempts == MAX_ATTEMPTS


def test_disabled_worker_never_claims_or_sends(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import app.payroll.delivery_worker as worker

    monkeypatch.setattr(settings, "PAYSLIP_DELIVERY_ENABLED", False)
    monkeypatch.setattr(worker, "HEARTBEAT_FILE", tmp_path / "heartbeat")
    monkeypatch.setattr(
        worker, "_claim_due_jobs", lambda: pytest.fail("claimed while disabled")
    )

    run_worker(once=True)


def test_worker_heartbeat_health_check_requires_recent_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.payroll.delivery_worker as worker

    marker = tmp_path / "worker-heartbeat"
    monkeypatch.setattr(worker, "HEARTBEAT_FILE", marker)
    assert worker.heartbeat_is_fresh(now=1_000_000) is False

    worker._write_heartbeat()
    assert worker.heartbeat_is_fresh(now=marker.stat().st_mtime + 60) is True
    assert worker.heartbeat_is_fresh(now=marker.stat().st_mtime + 60.01) is False
    assert worker.heartbeat_is_fresh(now=marker.stat().st_mtime - 1) is False


def test_enabled_worker_refreshes_heartbeat_between_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.payroll.delivery_worker as worker

    marker = tmp_path / "heartbeat"
    monkeypatch.setattr(worker, "HEARTBEAT_FILE", marker)
    monkeypatch.setattr(settings, "PAYSLIP_DELIVERY_ENABLED", True)
    monkeypatch.setattr(worker, "_claim_due_jobs", lambda: [uuid.uuid4(), uuid.uuid4()])
    monkeypatch.setattr(worker, "_send_job", lambda _: None)
    write_count = 0
    write_heartbeat = worker._write_heartbeat

    def count_heartbeat() -> None:
        nonlocal write_count
        write_count += 1
        write_heartbeat()

    monkeypatch.setattr(worker, "_write_heartbeat", count_heartbeat)
    run_worker(once=True)

    assert write_count == 4  # startup, after each job, and after the poll cycle
    assert worker.heartbeat_is_fresh() is True


def test_disabled_supervised_worker_stays_idle_without_claiming(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import app.payroll.delivery_worker as worker

    class StopIdleLoop(Exception):
        pass

    monkeypatch.setattr(settings, "PAYSLIP_DELIVERY_ENABLED", False)
    heartbeat = tmp_path / "heartbeat"
    monkeypatch.setattr(worker, "HEARTBEAT_FILE", heartbeat)
    monkeypatch.setattr(
        worker, "_claim_due_jobs", lambda: pytest.fail("claimed while disabled")
    )

    sleep_calls = 0

    def stop_after_one_poll(seconds: int) -> None:
        nonlocal sleep_calls
        assert seconds == worker.POLL_SECONDS
        sleep_calls += 1
        if sleep_calls == 1:
            os.utime(heartbeat, (0, 0))
            return
        raise StopIdleLoop

    monkeypatch.setattr(worker.time, "sleep", stop_after_one_poll)
    with pytest.raises(StopIdleLoop):
        run_worker()
    assert worker.heartbeat_is_fresh() is True
