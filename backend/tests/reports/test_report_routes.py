"""Phase B5 — report route tests."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.employee.models import EmployeeRecords, EmployeeStatus
from app.payroll.models import PayrollEntry, PayrollRun, PayrollRunStatus

API = settings.API_V1_STR


def test_payroll_summary_report(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    r = client.get(f"{API}/reports/payroll/summary", headers=superuser_token_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "data" in data
    assert "count" in data


def test_leave_balance_report(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    r = client.get(f"{API}/reports/leave-balance", headers=superuser_token_headers)
    assert r.status_code == 200, r.text


def test_attendance_summary_report(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    r = client.get(f"{API}/reports/attendance-summary", headers=superuser_token_headers)
    assert r.status_code == 200, r.text


def test_headcount_report(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    r = client.get(f"{API}/reports/headcount", headers=superuser_token_headers)
    assert r.status_code == 200, r.text


def _seed_run_with_entries(db: Session) -> tuple[uuid.UUID, list[PayrollEntry]]:
    run = PayrollRun(
        id=uuid.uuid4(),
        cutoff_type="monthly",
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 30),
        status=PayrollRunStatus.DRAFT,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    entries = []
    for gross, deductions in ((Decimal("25000.00"), Decimal("3000.00")), (Decimal("15000.00"), Decimal("2000.00"))):
        emp = EmployeeRecords(
            id=uuid.uuid4(),
            employee_code=f"RPT-{uuid.uuid4().hex[:6]}",
            first_name="Report",
            last_name="Employee",
            birthdate=date(1990, 1, 1),
            employee_status=EmployeeStatus.ACTIVE,
            is_deleted=False,
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)
        entry = PayrollEntry(
            id=uuid.uuid4(),
            payroll_run_id=run.id,
            employee_id=emp.id,
            basic_rate=gross,
            rate_date_from=date(2026, 9, 1),
            rate_date_to=date(2026, 9, 30),
            earnings={},
            deductions={},
            gross_pay=gross,
            total_deductions=deductions,
            net_pay=gross - deductions,
            overtime_pay=Decimal("0.00"),
            thirteenth_month=Decimal("0.00"),
            non_taxable_income=Decimal("0.00"),
            taxable_income=gross - deductions,
            is_deleted=False,
        )
        db.add(entry)
        entries.append(entry)
    db.commit()
    return run.id, entries


def test_payroll_summary_calculations(client: TestClient, superuser_token_headers: dict[str, str], db: Session) -> None:
    run_id, _ = _seed_run_with_entries(db)

    r = client.get(f"{API}/reports/payroll/summary?run_id={run_id}", headers=superuser_token_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run_id"] == str(run_id)
    assert body["count"] == 2
    assert body["totals"]["gross_pay"] == 40000.0
    assert body["totals"]["total_deductions"] == 5000.0
    assert body["totals"]["net_pay"] == 35000.0
    # Filtering by a different run returns nothing.
    other = client.get(f"{API}/reports/payroll/summary?run_id={uuid.uuid4()}", headers=superuser_token_headers)
    assert other.status_code == 200
    assert other.json()["count"] == 0
    assert other.json()["totals"]["gross_pay"] == 0.0
