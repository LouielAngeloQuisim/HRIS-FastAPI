"""Reviewed tax classification and year-to-date opening input API tests."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import EmployeeTaxBenefit, EmployeeTaxYearDeclaration
from app.payroll.routes import _bir_tax_benefit_rows

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
        "opening_as_of": "2026-06-30",
        "taxable_compensation_ytd": "120000.00",
        "tax_withheld_ytd": "5000.00",
        "opening_pay_period_count": 12,
        "opening_pay_period_type": "monthly",
        "previous_employer_included": True,
        "opening_benefits_exempt_ytd": "70000.00",
        "opening_benefits_reconciled": True,
        "opening_de_minimis_annual_ytd": {
            "uniform_clothing": "0.00",
            "actual_medical_assistance": "0.00",
            "achievement_award": "0.00",
            "christmas_anniversary_gift": "0.00",
            "cba_productivity_incentive": "0.00",
        },
        "opening_de_minimis_monthly_ytd": {
            "medical_cash_dependents": "0.00",
            "rice_subsidy": "0.00",
            "laundry_allowance": "0.00",
        },
        "source_reference": "BIR Form 2316 reviewed",
        "is_verified": True,
    }

    assert client.get(url, headers=superuser_token_headers).status_code == 404
    created = client.put(url, json=payload, headers=superuser_token_headers)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["employee_id"] == str(employee.id)
    assert body["tax_year"] == 2026
    assert body["opening_as_of"] == "2026-06-30"
    assert body["taxable_compensation_ytd"] == "120000.00"
    assert body["tax_withheld_ytd"] == "5000.00"
    assert body["opening_pay_period_count"] == 12
    assert body["opening_pay_period_type"] == "monthly"
    assert body["previous_employer_included"] is True
    assert body["opening_benefits_exempt_ytd"] == "70000.00"
    assert body["opening_benefits_reconciled"] is True
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


def test_tax_year_benefit_ledger_is_auditable_and_supports_one_full_reversal(
    client: TestClient,
    db: Session,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    url = f"{API}/employees/{employee_record.id}/tax-year-benefits/2026"
    payment = client.post(
        url,
        json={
            "paid_on": "2026-07-01",
            "benefit_type": "thirteenth_month",
            "gross_amount": "30000.00",
            "source_reference": "Voucher PV-2026-071 reviewed",
        },
        headers=superuser_token_headers,
    )
    assert payment.status_code == 201, payment.text
    original = payment.json()
    assert original["gross_amount"] == "30000.00"
    assert original["correction_of_id"] is None
    duplicate_payment = client.post(
        url,
        json={
            "paid_on": "2026-07-01",
            "benefit_type": "thirteenth_month",
            "gross_amount": "30000.00",
            "source_reference": "Voucher PV-2026-071 reviewed",
        },
        headers=superuser_token_headers,
    )
    assert duplicate_payment.status_code == 409

    invalid_partial_reversal = client.post(
        url,
        json={
            "paid_on": "2026-07-02",
            "benefit_type": "thirteenth_month",
            "gross_amount": "-10000.00",
            "source_reference": "Correction note 1",
            "correction_of_id": original["id"],
            "correction_reason": "Incorrect voucher total",
        },
        headers=superuser_token_headers,
    )
    assert invalid_partial_reversal.status_code == 422

    reversal_payload = {
        "paid_on": "2026-07-02",
        "benefit_type": "thirteenth_month",
        "gross_amount": "-30000.00",
        "source_reference": "Correction note 2",
        "correction_of_id": original["id"],
        "correction_reason": "Original voucher was entered twice",
    }
    reversal = client.post(url, json=reversal_payload, headers=superuser_token_headers)
    assert reversal.status_code == 201, reversal.text
    assert reversal.json()["correction_reason"] == reversal_payload["correction_reason"]
    assert reversal.json()["gross_amount"] == "-30000.00"

    duplicate_reversal = client.post(url, json=reversal_payload, headers=superuser_token_headers)
    assert duplicate_reversal.status_code == 409
    listed = client.get(url, headers=superuser_token_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 2
    assert sum(Decimal(item["gross_amount"]) for item in listed.json()) == Decimal("0.00")
    assert db.get(EmployeeTaxBenefit, uuid.UUID(original["id"])) is not None


def test_tax_year_benefit_ledger_requires_payroll_approval(
    client: TestClient,
    employee_record: EmployeeRecords,
    normal_user_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{API}/employees/{employee_record.id}/tax-year-benefits/2026",
        json={
            "paid_on": "2026-07-01",
            "benefit_type": "other_benefit",
            "gross_amount": "100.00",
            "source_reference": "Voucher PV-26-001",
        },
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_de_minimis_ledger_requires_category_and_conditional_evidence(
    client: TestClient,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    url = f"{API}/employees/{employee_record.id}/tax-year-benefits/2026"
    base = {
        "paid_on": "2026-07-01",
        "benefit_type": "de_minimis",
        "gross_amount": "12000.00",
        "source_reference": "Voucher PV-26-071",
    }

    missing_category = client.post(url, json=base, headers=superuser_token_headers)
    assert missing_category.status_code == 422

    missing_evidence = client.post(
        url,
        json={**base, "de_minimis_category": "actual_medical_assistance"},
        headers=superuser_token_headers,
    )
    assert missing_evidence.status_code == 422
    assert "actual_medical_documentation" in missing_evidence.text

    saved = client.post(
        url,
        json={
            **base,
            "de_minimis_category": "actual_medical_assistance",
            "eligibility_evidence": ["actual_medical_documentation"],
        },
        headers=superuser_token_headers,
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["de_minimis_category"] == "actual_medical_assistance"
    assert saved.json()["eligibility_evidence"] == ["actual_medical_documentation"]


def test_bir_benefit_ledger_applies_reconciled_category_opening_balances(
    db: Session, employee_record: EmployeeRecords
) -> None:
    db.add_all(
        [
            EmployeeTaxBenefit(
                employee_id=employee_record.id,
                tax_year=2026,
                paid_on=date(2026, 10, 20),
                benefit_type="de_minimis",
                de_minimis_category="rice_subsidy",
                gross_amount="1000.00",
                source_reference="Voucher rice October",
            ),
            EmployeeTaxBenefit(
                employee_id=employee_record.id,
                tax_year=2026,
                paid_on=date(2026, 10, 21),
                benefit_type="de_minimis",
                de_minimis_category="uniform_clothing",
                gross_amount="3000.00",
                source_reference="Voucher uniform October",
            ),
        ]
    )
    db.commit()

    rows = _bir_tax_benefit_rows(
        db,
        employee_record.id,
        2026,
        date(2026, 10, 15),
        date(2026, 10, 31),
        {"uniform_clothing": "6000.00"},
        {"rice_subsidy": "2000.00"},
    )

    by_category = {row["de_minimis_category"]: row for row in rows}
    assert by_category["rice_subsidy"]["category_exempt_amount"] == "500.00"
    assert by_category["rice_subsidy"]["category_excess_amount"] == "500.00"
    assert by_category["uniform_clothing"]["category_exempt_amount"] == "2000.00"
    assert by_category["uniform_clothing"]["category_excess_amount"] == "1000.00"


def test_previous_employer_requires_explicit_de_minimis_opening_balances(
    client: TestClient,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.put(
        f"{API}/employees/{employee_record.id}/tax-year-declarations/2026",
        json={
            "opening_as_of": "2026-06-30",
            "taxable_compensation_ytd": "100.00",
            "opening_pay_period_count": 6,
            "opening_pay_period_type": "semi_monthly",
            "previous_employer_included": True,
            "opening_benefits_reconciled": True,
            "source_reference": "Reviewed Form 2316",
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 422
    assert "explicit annual and monthly balances" in response.text


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
        json={"opening_as_of": "2027-01-01", "taxable_compensation_ytd": "-0.01"},
        headers=superuser_token_headers,
    ).status_code == 422


def test_previous_employer_declaration_requires_period_count_and_source_note(
    client: TestClient,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    url = f"{API}/employees/{employee_record.id}/tax-year-declarations/2026"
    base = {
        "opening_as_of": "2026-06-30",
        "taxable_compensation_ytd": "180000.00",
        "tax_withheld_ytd": "11000.40",
        "previous_employer_included": True,
        "opening_benefits_reconciled": True,
        "opening_de_minimis_annual_ytd": {
            "uniform_clothing": "0.00",
            "actual_medical_assistance": "0.00",
            "achievement_award": "0.00",
            "christmas_anniversary_gift": "0.00",
            "cba_productivity_incentive": "0.00",
        },
        "opening_de_minimis_monthly_ytd": {
            "medical_cash_dependents": "0.00",
            "rice_subsidy": "0.00",
            "laundry_allowance": "0.00",
        },
    }
    assert client.put(url, json=base, headers=superuser_token_headers).status_code == 422
    response = client.put(
        url,
        json={
            **base,
            "source_reference": "Form 2316 reviewed",
            "opening_pay_period_count": 6,
            "opening_pay_period_type": "semi_monthly",
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, response.text


def test_minimum_wage_earner_classification_requires_wage_order_evidence(
    client: TestClient,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    url = f"{API}/employees/{employee_record.id}/tax-year-declarations/2026"
    payload = {
        "tax_classification": "minimum_wage_earner",
        "opening_as_of": "2026-01-01",
        "is_verified": True,
    }
    missing_source = client.put(url, json=payload, headers=superuser_token_headers)
    assert missing_source.status_code == 422
    assert "DOLE wage order" in missing_source.text

    with_source = client.put(
        url,
        json={
            **payload,
            "source_reference": "DOLE Wage Order NCR-XX; assigned NCR workplace",
        },
        headers=superuser_token_headers,
    )
    assert with_source.status_code == 200, with_source.text
    assert with_source.json()["tax_classification"] == "minimum_wage_earner"
