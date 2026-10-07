"""Reviewed tax classification and year-to-date opening input API tests."""

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import EmployeeTaxYearDeclaration

API = f"{settings.API_V1_STR}/payroll"


@pytest.fixture
def employee_record(db: Session) -> EmployeeRecords:
    employee = EmployeeRecords(
        employee_code=f"TAX-{uuid.uuid4().hex[:8]}",
        first_name="Tax",
        last_name="Test",
        birthdate=date(1990, 1, 1),
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def test_tax_year_declaration_upsert_and_get(
    client: TestClient,
    db: Session,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    employee = employee_record
    url = f"{API}/employees/{employee.id}/tax-year-declarations/2026"
    payload = {
        "tax_classification": "ordinary",
        "taxable_compensation_ytd": "120000.00",
        "tax_withheld_ytd": "5000.00",
        "previous_employer_included": True,
        "source_reference": "BIR Form 2316 reviewed",
        "is_verified": True,
    }

    assert client.get(url, headers=superuser_token_headers).status_code == 404
    created = client.put(url, json=payload, headers=superuser_token_headers)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["employee_id"] == str(employee.id)
    assert body["tax_year"] == 2026
    assert body["taxable_compensation_ytd"] == "120000.00"
    assert body["tax_withheld_ytd"] == "5000.00"
    assert body["previous_employer_included"] is True
    assert body["is_verified"] is True
    assert body["verified_by"]
    assert body["verified_at"]

    updated = client.put(
        url,
        json={**payload, "taxable_compensation_ytd": "140000.00"},
        headers=superuser_token_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == body["id"]
    assert updated.json()["taxable_compensation_ytd"] == "140000.00"
    assert client.get(url, headers=superuser_token_headers).json()["id"] == body["id"]
    assert db.get(EmployeeTaxYearDeclaration, uuid.UUID(body["id"])) is not None


def test_tax_year_declaration_requires_approval_permission(
    client: TestClient,
    employee_record: EmployeeRecords,
    normal_user_token_headers: dict[str, str],
) -> None:
    url = f"{API}/employees/{employee_record.id}/tax-year-declarations/2026"
    response = client.put(
        url,
        json={"is_verified": True},
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_tax_year_declaration_rejects_invalid_year_and_negative_amounts(
    client: TestClient,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    base = f"{API}/employees/{employee_record.id}/tax-year-declarations"
    assert client.put(f"{base}/1999", json={}, headers=superuser_token_headers).status_code == 422
    assert client.put(
        f"{base}/2026",
        json={"taxable_compensation_ytd": "-0.01"},
        headers=superuser_token_headers,
    ).status_code == 422
