"""B4C verification scenarios — cross-check calculator outputs against official formulas.

These scenarios use the same bracket fixtures as test_calculator.py and
assert exact computed values so that future bracket-table edits or formula
drifts are caught immediately.
"""

import uuid
from collections.abc import Generator
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
def sss_brackets(db: Session) -> Generator[list[SSSBracket], None, None]:
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
            effective_date=date(2024, 7, 1),
        ),
    ]
    for b in brackets:
        db.add(b)
    db.commit()
    for b in brackets:
        db.refresh(b)
    yield brackets
    for b in brackets:
        db.delete(b)
    db.commit()


@pytest.fixture
def philhealth_brackets(db: Session) -> Generator[list[PhilHealthBracket], None, None]:
    brackets = [
        PhilHealthBracket(
            id=uuid.uuid4(),
            salary_min=10000.0,
            salary_max=100000.0,
            rate=5.0,
            employer_share=2.5,
            employee_share=2.5,
            effective_date=date(2024, 1, 1),
        ),
    ]
    for b in brackets:
        db.add(b)
    db.commit()
    for b in brackets:
        db.refresh(b)
    yield brackets
    for b in brackets:
        db.delete(b)
    db.commit()


@pytest.fixture
def pagibig_brackets(db: Session) -> Generator[list[PagIBIGBracket], None, None]:
    brackets = [
        PagIBIGBracket(
            id=uuid.uuid4(),
            salary_min=1000.0,
            salary_max=10000.0,
            employee_rate=2.0,
            employer_rate=2.0,
            effective_date=date(2024, 1, 1),
        ),
    ]
    for b in brackets:
        db.add(b)
    db.commit()
    for b in brackets:
        db.refresh(b)
    yield brackets
    for b in brackets:
        db.delete(b)
    db.commit()


@pytest.fixture
def bir_brackets(db: Session) -> Generator[list[BIRBracket], None, None]:
    brackets = [
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
            effective_date=date(2024, 7, 1),
        ),
        BIRBracket(
            id=uuid.uuid4(),
            period="monthly",
            bracket_min=20833.34,
            bracket_max=33333.33,
            base_tax=2083.33,
            excess_rate=30.0,
            effective_date=date(2024, 7, 1),
        ),
        BIRBracket(
            id=uuid.uuid4(),
            period="monthly",
            bracket_min=33333.34,
            bracket_max=None,
            base_tax=5833.33,
            excess_rate=32.0,
            effective_date=date(2024, 7, 1),
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
            effective_date=date(2024, 7, 1),
        ),
        BIRBracket(
            id=uuid.uuid4(),
            period="daily",
            bracket_min=1388.90,
            bracket_max=2222.22,
            base_tax=277.78,
            excess_rate=30.0,
            effective_date=date(2024, 7, 1),
        ),
    ]
    for b in brackets:
        db.add(b)
    db.commit()
    for b in brackets:
        db.refresh(b)
    yield brackets
    for b in brackets:
        db.delete(b)
    db.commit()


def _create_employee_with_salary(db: Session, basic_rate: Decimal, pay_type: str = "monthly") -> EmployeeRecords:
    emp = EmployeeRecords(
        employee_code=f"EMP-{uuid.uuid4().hex[:8]}",
        first_name="Verify",
        last_name="Scenario",
        birthdate=date(1990, 1, 1),
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)

    salary = EmployeeSalary(
        employee_id=emp.id,
        basic_rate=basic_rate,
        currency="PHP",
        effective_date=date(2024, 1, 1),
        pay_type=pay_type,
    )
    db.add(salary)
    db.commit()
    db.refresh(salary)
    return emp


class TestOfficialWorkedExamples:
    """Scenario 2: Semi-monthly ₱25,000, no OT."""

    def test_monthly_25000_no_ot(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        sss_brackets: list[SSSBracket],
        philhealth_brackets: list[PhilHealthBracket],
        pagibig_brackets: list[PagIBIGBracket],
        bir_brackets: list[BIRBracket],
        db: Session,
    ) -> None:
        emp = _create_employee_with_salary(db, Decimal("25000.00"))
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [str(emp.id)],
        }
        resp = client.post(f"{API}/runs/preview", json=payload, headers=superuser_token_headers)
        assert resp.status_code == 200, resp.text
        entry = resp.json()["entries"][0]

        # SSS: MSC=25000 falls in 10001-35000 bracket, employee_ss=875
        assert Decimal(str(entry["deductions"]["sss_employee"])) == pytest.approx(Decimal("875.0"), abs=Decimal("0.01"))
        # PhilHealth: 25000 * 0.05 / 2 = 625
        assert Decimal(str(entry["deductions"]["philhealth_employee"])) == pytest.approx(Decimal("625.0"), abs=Decimal("0.01"))
        # Pag-IBIG: min(25000, 10000) * 0.02 = 200
        assert Decimal(str(entry["deductions"]["pagibig_employee"])) == pytest.approx(Decimal("200.0"), abs=Decimal("0.01"))
        # Taxable = 25000 - 875 - 625 - 200 = 23300
        assert Decimal(entry["taxable_income"]) == pytest.approx(Decimal("23300.0"), abs=Decimal("0.01"))


class TestHighEarnerMonthly:
    """Scenario 5: High earner ₱200,000/mo, monthly cutoff."""

    def test_high_earner_monthly(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        sss_brackets: list[SSSBracket],
        philhealth_brackets: list[PhilHealthBracket],
        pagibig_brackets: list[PagIBIGBracket],
        bir_brackets: list[BIRBracket],
        db: Session,
    ) -> None:
        emp = _create_employee_with_salary(db, Decimal("200000.00"))
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [str(emp.id)],
        }
        resp = client.post(f"{API}/runs/preview", json=payload, headers=superuser_token_headers)
        assert resp.status_code == 200, resp.text
        entry = resp.json()["entries"][0]

        # SSS: capped at 35000, employee_ss=875
        assert Decimal(str(entry["deductions"]["sss_employee"])) == pytest.approx(Decimal("875.0"), abs=Decimal("0.01"))
        # PhilHealth: capped at 100000, 100000 * 0.05 / 2 = 2500
        assert Decimal(str(entry["deductions"]["philhealth_employee"])) == pytest.approx(Decimal("2500.0"), abs=Decimal("0.01"))
        # Pag-IBIG: capped at 10000, 10000 * 0.02 = 200
        assert Decimal(str(entry["deductions"]["pagibig_employee"])) == pytest.approx(Decimal("200.0"), abs=Decimal("0.01"))
        # Taxable = 200000 - 875 - 2500 - 200 = 196425
        assert Decimal(entry["taxable_income"]) == pytest.approx(Decimal("196425.0"), abs=Decimal("0.01"))


class TestMidPeriodRateChange:
    """Scenario 7: Rate change mid-period."""

    def test_rate_change_mid_period(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        sss_brackets: list[SSSBracket],
        philhealth_brackets: list[PhilHealthBracket],
        pagibig_brackets: list[PagIBIGBracket],
        bir_brackets: list[BIRBracket],
        db: Session,
    ) -> None:
        emp = EmployeeRecords(
            employee_code=f"EMP-{uuid.uuid4().hex[:8]}",
            first_name="Verify",
            last_name="RateChange",
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
        entry = resp.json()["entries"][0]

        # Pro-rated basic pay: 30000/31*14 + 20000/31*17 = 24516.13
        expected_basic = (
            Decimal("30000.00") / 31 * 14 + Decimal("20000.00") / 31 * 17
        ).quantize(Decimal("0.01"))
        assert Decimal(entry["basic_rate"]) == pytest.approx(expected_basic, abs=Decimal("0.01"))


class TestEmployeeNoSalaryRecord:
    """Scenario 13: Employee with no salary record."""

    def test_no_salary_record_returns_error(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        emp = EmployeeRecords(
            employee_code=f"EMP-{uuid.uuid4().hex[:8]}",
            first_name="Verify",
            last_name="NoSalary",
            birthdate=date(1990, 1, 1),
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)

        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [str(emp.id)],
        }
        resp = client.post(f"{API}/runs/preview", json=payload, headers=superuser_token_headers)
        assert resp.status_code == 422, resp.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
