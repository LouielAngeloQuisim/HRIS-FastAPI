"""Guard legacy payroll runs from entering the new immutable review flow."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import PayrollEntry, PayrollRun, PayrollRunStatus
from app.user.models import User

API = f"{settings.API_V1_STR}/payroll"


def _legacy_run(db: Session) -> PayrollRun:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    run = PayrollRun(
        cutoff_type="monthly",
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 30),
        status=PayrollRunStatus.DRAFT,
        adjustment_type="regular",
        created_by=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_legacy_run_cannot_enter_new_review_workflow(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    run = _legacy_run(db)
    response = client.post(
        f"{API}/runs/{run.id}/start-review", headers=superuser_token_headers
    )
    assert response.status_code == 409
    db.refresh(run)
    assert run.workflow_status == "draft"


def test_legacy_run_cannot_be_finalized(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    run = _legacy_run(db)
    response = client.post(
        f"{API}/runs/{run.id}/finalize", headers=superuser_token_headers
    )
    assert response.status_code == 503
    assert "disabled until HR approves" in response.json()["detail"]
    db.refresh(run)
    assert run.status == PayrollRunStatus.DRAFT
    assert run.frozen_snapshot is None


def test_authorized_payroll_user_can_read_draft_for_review(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    run = _legacy_run(db)
    response = client.get(f"{API}/runs/{run.id}", headers=superuser_token_headers)
    assert response.status_code == 200, response.text
    assert response.json()["workflow_status"] == "draft"
    assert (
        response.json()["payroll_finalization_enabled"]
        is settings.PAYROLL_FINALIZATION_ENABLED
    )
    assert (
        response.json()["payslip_delivery_enabled"] is settings.PAYSLIP_DELIVERY_ENABLED
    )


def test_payroll_run_detail_includes_employee_name_and_code(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    run = _legacy_run(db)
    employee = EmployeeRecords(
        employee_code="QA-PAY-DETAIL",
        first_name="Ava",
        last_name="Worker",
        birthdate=date(1990, 1, 1),
    )
    db.add(employee)
    db.flush()
    db.add(
        PayrollEntry(
            payroll_run_id=run.id,
            employee_id=employee.id,
            basic_rate=Decimal("1000.00"),
            rate_date_from=date(2026, 9, 1),
            rate_date_to=date(2026, 9, 30),
            gross_pay=Decimal("1000.00"),
            total_deductions=Decimal("0.00"),
            net_pay=Decimal("1000.00"),
            taxable_income=Decimal("1000.00"),
        )
    )
    db.commit()

    response = client.get(f"{API}/runs/{run.id}", headers=superuser_token_headers)

    assert response.status_code == 200, response.text
    entry = response.json()["entries"][0]
    assert entry["employee_name"] == "Ava Worker"
    assert entry["employee_code"] == "QA-PAY-DETAIL"
