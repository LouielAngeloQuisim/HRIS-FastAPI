"""Authenticated PDF access is limited to frozen, finalized payslip snapshots."""

from datetime import date
from decimal import Decimal
from typing import Callable

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select
import pytest

from app.common.audit.sink import AuditRecord, AuditSink, LogSink, set_audit_sink
from app.config.settings import settings
from app.payroll.models import (
    PayrollDeliveryOutbox,
    PayrollEntry,
    PayrollRun,
    PayrollRunStatus,
)
from app.user.models import User

API = f"{settings.API_V1_STR}/payroll"


class CapturingAuditSink(AuditSink):
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def emit(self, record: AuditRecord) -> None:
        self.records.append(record)


def _run_and_entry(db: Session, *, finalized: bool) -> tuple[PayrollRun, PayrollEntry]:
    preparer = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    run = PayrollRun(
        cutoff_type="monthly",
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 30),
        status=PayrollRunStatus.APPROVED if finalized else PayrollRunStatus.DRAFT,
        adjustment_type="regular",
        created_by=preparer.id,
        workflow_status="finalized" if finalized else "draft",
        frozen_snapshot={"run_id": "frozen"} if finalized else None,
    )
    db.add(run)
    db.flush()
    entry = PayrollEntry(
        payroll_run_id=run.id,
        employee_id=None,
        basic_rate=Decimal("1000.00"),
        rate_date_from=date(2026, 9, 1),
        rate_date_to=date(2026, 9, 30),
        gross_pay=Decimal("1000.00"),
        total_deductions=Decimal("100.00"),
        net_pay=Decimal("900.00"),
        taxable_income=Decimal("1000.00"),
    )
    db.add(entry)
    db.flush()
    if finalized:
        db.add(
            PayrollDeliveryOutbox(
                payroll_entry_id=entry.id,
                document_version=1,
                status="blocked_email",
                content_snapshot={
                    "entry": {
                        "employee": {"name": "Fictional Worker", "code": "QA-1"},
                        "amounts": {
                            "gross": "1000.00",
                            "deductions": "100.00",
                            "net": "900.00",
                            "earnings": {"regular": "1000.00"},
                            "deduction_lines": {"bir": "100.00"},
                        },
                    },
                    "run": {
                        "period": {"from": "2026-09-01", "to": "2026-09-30"},
                        "payment_date": "2026-10-05",
                    },
                },
            )
        )
    db.commit()
    db.refresh(run)
    db.refresh(entry)
    return run, entry


@pytest.fixture
def payslip_records(db: Session) -> Callable[[bool], tuple[PayrollRun, PayrollEntry]]:
    created: list[tuple[PayrollRun, PayrollEntry]] = []

    def create(finalized: bool) -> tuple[PayrollRun, PayrollEntry]:
        records = _run_and_entry(db, finalized=finalized)
        created.append(records)
        return records

    yield create

    for run, entry in created:
        db.exec(
            delete(PayrollDeliveryOutbox).where(
                PayrollDeliveryOutbox.payroll_entry_id == entry.id
            )
        )
        db.exec(delete(PayrollEntry).where(PayrollEntry.id == entry.id))
        db.exec(delete(PayrollRun).where(PayrollRun.id == run.id))
    db.commit()


def test_draft_payslip_download_is_rejected(
    client: TestClient,
    payslip_records: Callable[[bool], tuple[PayrollRun, PayrollEntry]],
    superuser_token_headers: dict[str, str],
) -> None:
    run, entry = payslip_records(False)

    response = client.get(
        f"{API}/runs/{run.id}/entries/{entry.id}/payslip.pdf",
        headers=superuser_token_headers,
    )

    assert response.status_code == 409
    assert "only after the payroll run is finalized" in response.json()["detail"]


def test_finalized_payslip_download_is_private_and_audited(
    client: TestClient,
    payslip_records: Callable[[bool], tuple[PayrollRun, PayrollEntry]],
    superuser_token_headers: dict[str, str],
) -> None:
    run, entry = payslip_records(True)
    sink = CapturingAuditSink()
    set_audit_sink(sink)
    try:
        response = client.get(
            f"{API}/runs/{run.id}/entries/{entry.id}/payslip.pdf",
            headers=superuser_token_headers,
        )
    finally:
        set_audit_sink(LogSink())

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content.startswith(b"%PDF-")
    assert len(sink.records) == 1
    assert sink.records[0].module == "payroll"
    assert sink.records[0].action == "payslip_download"
    assert sink.records[0].user_id is not None
