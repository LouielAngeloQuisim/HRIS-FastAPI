"""Explicit salary increments are effective-dated, previewed and replay-safe."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import EmployeeSalary

API = f"{settings.API_V1_STR}/payroll"


def test_selected_salary_increment_previews_commits_and_replays(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    employee = EmployeeRecords(
        employee_code=f"INC-{uuid.uuid4().hex[:8]}",
        first_name="Increment",
        last_name="QA",
        birthdate=date(1990, 1, 1),
    )
    db.add(employee)
    db.flush()
    original = EmployeeSalary(
        employee_id=employee.id,
        basic_rate=Decimal("15000.00"),
        effective_date=date(2026, 1, 1),
        pay_type="monthly",
        overtime_rate=Decimal("120.000"),
        non_taxable_allowance=Decimal("500.00"),
        de_minimis_monthly={"rice_subsidy": "1000.00"},
    )
    db.add(original)
    db.commit()

    filtered_roster = client.get(
        f"{API}/salary-roster",
        params={"search": employee.employee_code, "skip": 0, "limit": 10},
        headers=superuser_token_headers,
    )
    assert filtered_roster.status_code == 200
    assert filtered_roster.json()["count"] == 1
    assert filtered_roster.json()["data"][0]["employee_code"] == employee.employee_code

    request = {
        "batch_id": str(uuid.uuid4()),
        "effective_date": "2026-11-01",
        "increment": "50.00",
        "employee_ids": [str(employee.id)],
    }
    preview = client.post(
        f"{API}/salaries/bulk/increment/preview",
        json=request,
        headers=superuser_token_headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["valid"] is True
    assert preview.json()["changes"][0]["current_rate"] == "15000.00"
    assert preview.json()["changes"][0]["proposed_rate"] == "15050.00"

    saved = client.post(
        f"{API}/salaries/bulk/increment/commit",
        json=request,
        headers=superuser_token_headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["replayed"] is False
    assert saved.json()["salaries"][0]["basic_rate"] == "15050.00"
    assert saved.json()["salaries"][0]["overtime_rate"] == "120.000"
    assert saved.json()["salaries"][0]["non_taxable_allowance"] == "500.00"

    replay = client.post(
        f"{API}/salaries/bulk/increment/commit",
        json=request,
        headers=superuser_token_headers,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True
    rows = db.exec(
        select(EmployeeSalary).where(EmployeeSalary.employee_id == employee.id)
    ).all()
    assert len(rows) == 2


def test_salary_increment_blocks_missing_salary_without_writing(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    configured = EmployeeRecords(
        employee_code=f"INC-{uuid.uuid4().hex[:8]}",
        first_name="Configured",
        last_name="Salary",
        birthdate=date(1990, 1, 1),
    )
    missing = EmployeeRecords(
        employee_code=f"INC-{uuid.uuid4().hex[:8]}",
        first_name="Missing",
        last_name="Salary",
        birthdate=date(1990, 1, 1),
    )
    db.add_all([configured, missing])
    db.flush()
    original = EmployeeSalary(
        employee_id=configured.id,
        basic_rate=Decimal("15000.00"),
        effective_date=date(2026, 1, 1),
        pay_type="monthly",
    )
    db.add(original)
    db.commit()
    batch_request = {
        "batch_id": str(uuid.uuid4()),
        "effective_date": "2026-11-01",
        "increment": "50.00",
        "employee_ids": [str(configured.id), str(missing.id)],
    }
    response = client.post(
        f"{API}/salaries/bulk/increment/preview",
        json=batch_request,
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["issues"][0]["code"] == "salary_missing"
    commit = client.post(
        f"{API}/salaries/bulk/increment/commit",
        json=batch_request,
        headers=superuser_token_headers,
    )
    assert commit.status_code == 422
    configured_history = db.exec(
        select(EmployeeSalary).where(EmployeeSalary.employee_id == configured.id)
    ).all()
    assert len(configured_history) == 1
    assert configured_history[0].basic_rate == Decimal("15000.00")


def test_salary_increment_preserves_mixed_bases_in_one_explicit_batch(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    employees = [
        EmployeeRecords(
            employee_code=f"INC-{uuid.uuid4().hex[:8]}",
            first_name="Mixed",
            last_name=f"Basis {index}",
            birthdate=date(1990, 1, 1),
        )
        for index in range(2)
    ]
    db.add_all(employees)
    db.flush()
    db.add_all(
        [
            EmployeeSalary(
                employee_id=employees[0].id,
                basic_rate=Decimal("15000.00"),
                effective_date=date(2026, 1, 1),
                pay_type="monthly",
            ),
            EmployeeSalary(
                employee_id=employees[1].id,
                basic_rate=Decimal("1000.00"),
                effective_date=date(2026, 1, 1),
                pay_type="daily",
            ),
        ]
    )
    db.commit()

    request = {
        "batch_id": str(uuid.uuid4()),
        "effective_date": "2026-11-01",
        "increment": "50.00",
        "employee_ids": [str(employee.id) for employee in employees],
    }
    response = client.post(
        f"{API}/salaries/bulk/increment/preview",
        json=request,
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True
    changes = {row["employee_id"]: row for row in response.json()["changes"]}
    assert changes[str(employees[0].id)]["proposed_rate"] == "15050.00"
    assert changes[str(employees[0].id)]["pay_type"] == "monthly"
    assert changes[str(employees[1].id)]["proposed_rate"] == "1050.00"
    assert changes[str(employees[1].id)]["pay_type"] == "daily"

    committed = client.post(
        f"{API}/salaries/bulk/increment/commit",
        json=request,
        headers=superuser_token_headers,
    )
    assert committed.status_code == 200, committed.text
    assert {row["pay_type"] for row in committed.json()["salaries"]} == {"monthly", "daily"}
