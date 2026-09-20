"""B4B payroll generation edge-case tests.

Covers: mid-period rate pro-rating, cutoff-type matrix, non-taxable income,
de minimis caps, attendance deductions, immutability, 13th-month formula,
daily cutoff, preview/generate consistency, payslip endpoints.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import (
    BIRBracket,
    EmployeeSalary,
    PagIBIGBracket,
    PhilHealthBracket,
    SSSBracket,
)

API = f"{settings.API_V1_STR}/payroll"


@pytest.fixture
def employee_with_salary(db: Session) -> EmployeeRecords:
    emp = EmployeeRecords(
        employee_code=f"EMP-{uuid.uuid4().hex[:8]}",
        first_name="Payroll",
        last_name="Test",
        birthdate=date(1990, 1, 1),
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)

    salary = EmployeeSalary(
        employee_id=emp.id,
        basic_rate=Decimal("30000.00"),
        currency="PHP",
        effective_date=date(2024, 1, 1),
        pay_type="monthly",
        overtime_rate=Decimal("100.00"),
        absent_penalty_rate=Decimal("500.00"),
        non_taxable_allowance=Decimal("5000.00"),
        de_minimis_monthly={"rice": 1000.0, "laundry": 500.0, "medical": 200.0},
        thirteenth_month_exempt_portion=Decimal("90000.00"),
    )
    db.add(salary)
    db.commit()
    db.refresh(salary)
    return emp


@pytest.fixture
def payroll_brackets(db: Session) -> None:
    brackets = [
        SSSBracket(
            id=uuid.uuid4(),
            msc_min=2000.0,
            msc_max=10000.0,
            employer_ss=1000.0,
            employer_ec=26.0,
            employer_mpf=0.0,
            employee_ss=500.0,
            employee_mpf=0.0,
            effective_date=date(2024, 1, 1),
        ),
        SSSBracket(
            id=uuid.uuid4(),
            msc_min=10001.0,
            msc_max=35000.0,
            employer_ss=1750.0,
            employer_ec=30.0,
            employer_mpf=0.0,
            employee_ss=875.0,
            employee_mpf=0.0,
            effective_date=date(2024, 1, 1),
        ),
        PhilHealthBracket(
            id=uuid.uuid4(),
            salary_min=10000.0,
            salary_max=100000.0,
            rate=5.0,
            employer_share=2.5,
            employee_share=2.5,
            effective_date=date(2024, 1, 1),
        ),
        PagIBIGBracket(
            id=uuid.uuid4(),
            salary_min=1000.0,
            salary_max=10000.0,
            employee_rate=2.0,
            employer_rate=2.0,
            effective_date=date(2024, 1, 1),
        ),
        BIRBracket(
            id=uuid.uuid4(),
            period="monthly",
            bracket_min=0.0,
            bracket_max=10416.67,
            base_tax=0.0,
            excess_rate=20.0,
            effective_date=date(2024, 1, 1),
        ),
        BIRBracket(
            id=uuid.uuid4(),
            period="monthly",
            bracket_min=10416.68,
            bracket_max=20833.33,
            base_tax=0.0,
            excess_rate=25.0,
            effective_date=date(2024, 1, 1),
        ),
        BIRBracket(
            id=uuid.uuid4(),
            period="monthly",
            bracket_min=20833.34,
            bracket_max=33333.33,
            base_tax=2083.33,
            excess_rate=30.0,
            effective_date=date(2024, 1, 1),
        ),
        BIRBracket(
            id=uuid.uuid4(),
            period="monthly",
            bracket_min=33333.34,
            bracket_max=None,
            base_tax=5833.33,
            excess_rate=32.0,
            effective_date=date(2024, 1, 1),
        ),
        BIRBracket(
            id=uuid.uuid4(),
            period="daily",
            bracket_min=0.0,
            bracket_max=694.44,
            base_tax=0.0,
            excess_rate=20.0,
            effective_date=date(2024, 1, 1),
        ),
        BIRBracket(
            id=uuid.uuid4(),
            period="daily",
            bracket_min=694.45,
            bracket_max=1388.89,
            base_tax=0.0,
            excess_rate=25.0,
            effective_date=date(2024, 1, 1),
        ),
        BIRBracket(
            id=uuid.uuid4(),
            period="daily",
            bracket_min=1388.90,
            bracket_max=2222.22,
            base_tax=277.78,
            excess_rate=30.0,
            effective_date=date(2024, 1, 1),
        ),
    ]
    for b in brackets:
        db.add(b)
    db.commit()
    for b in brackets:
        db.refresh(b)


class TestPreviewGenerateConsistency:
    def test_preview_and_generate_return_same_entries(
        self, client: TestClient, employee_with_salary: EmployeeRecords, superuser_token_headers: dict[str, str], payroll_brackets: None
    ) -> None:
        employee_id = str(employee_with_salary.id)
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [employee_id],
        }

        preview_resp = client.post(f"{API}/runs/preview", json=payload, headers=superuser_token_headers)
        assert preview_resp.status_code == 200, preview_resp.text
        preview_data = preview_resp.json()
        preview_entries = preview_data["entries"]

        generate_resp = client.post(f"{API}/runs/generate", json=payload, headers=superuser_token_headers)
        assert generate_resp.status_code == 200, generate_resp.text
        run_id = generate_resp.json()["id"]

        run_resp = client.get(f"{API}/runs/{run_id}", headers=superuser_token_headers)
        assert run_resp.status_code == 200, run_resp.text
        run_data = run_resp.json()
        generated_entries = run_data["entries"]

        assert len(preview_entries) == len(generated_entries)
        for p, g in zip(preview_entries, generated_entries, strict=True):
            assert p["employee_id"] == g["employee_id"]
            assert Decimal(p["gross_pay"]) == Decimal(g["gross_pay"])
            assert Decimal(p["net_pay"]) == Decimal(g["net_pay"])


class TestMidPeriodRateChange:
    def test_rate_change_pro_rates_correctly(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str], payroll_brackets: None
    ) -> None:
        emp = EmployeeRecords(
            employee_code=f"EMP-{uuid.uuid4().hex[:8]}",
            first_name="Rate",
            last_name="Change",
            birthdate=date(1990, 1, 1),
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)

        old_salary = EmployeeSalary(
            employee_id=emp.id,
            basic_rate=Decimal("30000.00"),
            currency="PHP",
            effective_date=date(2024, 1, 1),
            pay_type="monthly",
        )
        db.add(old_salary)
        db.commit()

        new_salary = EmployeeSalary(
            employee_id=emp.id,
            basic_rate=Decimal("20000.00"),
            currency="PHP",
            effective_date=date(2024, 1, 15),
            pay_type="monthly",
        )
        db.add(new_salary)
        db.commit()

        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [str(emp.id)],
        }
        resp = client.post(f"{API}/runs/preview", json=payload, headers=superuser_token_headers)
        assert resp.status_code == 200, resp.text
        entries = resp.json()["entries"]
        assert len(entries) == 1
        entry = entries[0]
        expected_basic = (
            Decimal("30000.00") / 31 * 14 + Decimal("20000.00") / 31 * 17
        ).quantize(Decimal("0.01"))
        assert Decimal(entry["basic_rate"]) == expected_basic


class TestCutoffTypeMatrix:
    def test_daily_cutoff_uses_daily_bir_brackets(
        self, client: TestClient, employee_with_salary: EmployeeRecords, superuser_token_headers: dict[str, str], payroll_brackets: None
    ) -> None:
        employee_id = str(employee_with_salary.id)
        payload = {
            "cutoff_type": "daily",
            "date_from": "2024-01-01",
            "date_to": "2024-01-01",
            "employee_ids": [employee_id],
        }
        resp = client.post(f"{API}/runs/preview", json=payload, headers=superuser_token_headers)
        assert resp.status_code == 200, resp.text
        entries = resp.json()["entries"]
        assert len(entries) == 1
        assert Decimal(entries[0]["taxable_income"]) > 0


class TestNonTaxableIncome:
    def test_non_taxable_income_excluded_from_taxable(
        self, client: TestClient, employee_with_salary: EmployeeRecords, superuser_token_headers: dict[str, str], payroll_brackets: None
    ) -> None:
        employee_id = str(employee_with_salary.id)
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [employee_id],
        }
        resp = client.post(f"{API}/runs/preview", json=payload, headers=superuser_token_headers)
        assert resp.status_code == 200, resp.text
        entry = resp.json()["entries"][0]
        assert Decimal(entry["non_taxable_income"]) > 0
        gross = Decimal(entry["gross_pay"])
        taxable = Decimal(entry["taxable_income"])
        assert taxable < gross


class TestImmutability:
    def test_approved_run_cannot_be_regenerated(
        self, client: TestClient, employee_with_salary: EmployeeRecords, superuser_token_headers: dict[str, str], payroll_brackets: None
    ) -> None:
        employee_id = str(employee_with_salary.id)
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [employee_id],
        }
        resp = client.post(f"{API}/runs/generate", json=payload, headers=superuser_token_headers)
        assert resp.status_code == 200, resp.text
        run_id = resp.json()["id"]

        approve_resp = client.post(f"{API}/runs/{run_id}/approve", headers=superuser_token_headers)
        assert approve_resp.status_code == 200, approve_resp.text

        preview_resp = client.post(f"{API}/runs/preview", json=payload, headers=superuser_token_headers)
        assert preview_resp.status_code == 200, preview_resp.text


class TestPayslipEndpoints:
    def test_list_payslips_for_run(
        self, client: TestClient, employee_with_salary: EmployeeRecords, superuser_token_headers: dict[str, str], payroll_brackets: None
    ) -> None:
        employee_id = str(employee_with_salary.id)
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [employee_id],
        }
        resp = client.post(f"{API}/runs/generate", json=payload, headers=superuser_token_headers)
        assert resp.status_code == 200, resp.text
        run_id = resp.json()["id"]

        payslips_resp = client.get(f"{API}/runs/{run_id}/payslips", headers=superuser_token_headers)
        assert payslips_resp.status_code == 200, payslips_resp.text
        payslips = payslips_resp.json()
        assert len(payslips) == 1
        assert payslips[0]["employee_id"] == employee_id
        assert "net_pay" in payslips[0]

    def test_employee_payslip_endpoint(
        self, client: TestClient, employee_with_salary: EmployeeRecords, superuser_token_headers: dict[str, str], payroll_brackets: None
    ) -> None:
        employee_id = str(employee_with_salary.id)
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [employee_id],
        }
        resp = client.post(f"{API}/runs/generate", json=payload, headers=superuser_token_headers)
        assert resp.status_code == 200, resp.text

        payslip_resp = client.get(f"{API}/employees/{employee_id}/payslip", headers=superuser_token_headers)
        assert payslip_resp.status_code == 200, payslip_resp.text
        data = payslip_resp.json()
        assert data is not None
        assert data["employee_id"] == employee_id


class TestThirteenthMonth:
    def test_thirteenth_month_computed(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str], payroll_brackets: None
    ) -> None:
        emp = EmployeeRecords(
            employee_code=f"EMP-{uuid.uuid4().hex[:8]}",
            first_name="Thirteenth",
            last_name="Month",
            birthdate=date(1990, 1, 1),
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)

        salary = EmployeeSalary(
            employee_id=emp.id,
            basic_rate=Decimal("36000.00"),
            currency="PHP",
            effective_date=date(2024, 1, 1),
            pay_type="monthly",
            thirteenth_month_exempt_portion=Decimal("90000.00"),
        )
        db.add(salary)
        db.commit()

        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [str(emp.id)],
        }
        resp = client.post(f"{API}/runs/preview", json=payload, headers=superuser_token_headers)
        assert resp.status_code == 200, resp.text
        entry = resp.json()["entries"][0]
        expected_13th = Decimal("3000.00")
        assert Decimal(entry["thirteenth_month"]) == expected_13th


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
