"""Explicit, period-boundary pay-group batches are atomic and replay-safe."""

import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import (
    EmployeePayGroupAssignment,
    PayrollPayGroup,
)

API = f"{settings.API_V1_STR}/payroll"


def _employee(db: Session) -> EmployeeRecords:
    employee = EmployeeRecords(
        employee_code=f"PG-{uuid.uuid4().hex[:8]}",
        first_name="Pay",
        last_name="Group",
        birthdate=date(1990, 1, 1),
    )
    db.add(employee)
    db.flush()
    return employee


def _group(db: Session, cadence: str = "monthly") -> PayrollPayGroup:
    group = PayrollPayGroup(
        code=f"PG-{uuid.uuid4().hex[:8]}",
        name=f"QA {cadence} group",
        cadence=cadence,
        first_period_end_day=15 if cadence == "semi_monthly" else None,
        second_period_end_day=31 if cadence == "semi_monthly" else None,
        weekend_rule="next_business_day",
    )
    db.add(group)
    db.flush()
    return group


def test_bulk_transfer_closes_previous_assignment_and_replays(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    employee = _employee(db)
    old_group = _group(db)
    new_group = _group(db)
    old_assignment = EmployeePayGroupAssignment(
        employee_id=employee.id,
        pay_group_id=old_group.id,
        effective_from=date(2026, 10, 1),
    )
    db.add(old_assignment)
    db.commit()
    payload = {
        "batch_id": str(uuid.uuid4()),
        "pay_group_id": str(new_group.id),
        "effective_from": "2026-11-01",
        "employee_ids": [str(employee.id)],
    }

    response = client.post(
        f"{API}/pay-group-assignments/bulk/commit",
        json=payload,
        headers=superuser_token_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["replayed"] is False
    assignments = db.exec(
        select(EmployeePayGroupAssignment)
        .where(EmployeePayGroupAssignment.employee_id == employee.id)
        .order_by(EmployeePayGroupAssignment.effective_from)
    ).all()
    assert len(assignments) == 2
    assert assignments[0].effective_to == date(2026, 10, 31)
    assert assignments[1].pay_group_id == new_group.id
    assert assignments[1].effective_from == date(2026, 11, 1)
    assert assignments[1].effective_to is None

    replay = client.post(
        f"{API}/pay-group-assignments/bulk/commit",
        json=payload,
        headers=superuser_token_headers,
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["replayed"] is True
    assert len(
        db.exec(
            select(EmployeePayGroupAssignment).where(
                EmployeePayGroupAssignment.employee_id == employee.id
            )
        ).all()
    ) == 2


def test_bulk_assignment_requires_shared_period_boundary(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    employee = _employee(db)
    group = _group(db)
    db.commit()
    payload = {
        "batch_id": str(uuid.uuid4()),
        "pay_group_id": str(group.id),
        "effective_from": "2026-11-02",
        "employee_ids": [str(employee.id)],
    }

    preflight = client.post(
        f"{API}/pay-group-assignments/bulk/preflight",
        json=payload,
        headers=superuser_token_headers,
    )
    assert preflight.status_code == 200, preflight.text
    assert preflight.json()["valid"] is False
    assert preflight.json()["issues"][0]["code"] == "not_pay_period_boundary"
    commit = client.post(
        f"{API}/pay-group-assignments/bulk/commit",
        json=payload,
        headers=superuser_token_headers,
    )
    assert commit.status_code == 422
    assert not db.exec(
        select(EmployeePayGroupAssignment).where(
            EmployeePayGroupAssignment.employee_id == employee.id
        )
    ).all()


def test_bulk_assignment_rejects_invalid_row_without_partial_save(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    employee = _employee(db)
    group = _group(db)
    db.commit()
    payload = {
        "batch_id": str(uuid.uuid4()),
        "pay_group_id": str(group.id),
        "effective_from": "2026-11-01",
        "employee_ids": [str(employee.id), str(uuid.uuid4())],
    }

    response = client.post(
        f"{API}/pay-group-assignments/bulk/commit",
        json=payload,
        headers=superuser_token_headers,
    )
    assert response.status_code == 422
    assert "no assignments were saved" in response.text
    assert not db.exec(
        select(EmployeePayGroupAssignment).where(
            EmployeePayGroupAssignment.employee_id == employee.id
        )
    ).all()
