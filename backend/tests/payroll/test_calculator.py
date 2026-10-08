"""Tight assertions for payroll calculator endpoints.

Verifies complete response shapes, exact deterministic values, boundary rows,
contribution/tax/share relationships, validation-error envelope, and list-endpoint payloads.
"""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.attendance.models import EmployeeShiftAssignment, Shift
from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import (
    BIRBracket,
    EmployeeSalary,
    PagIBIGBracket,
    PayrollPolicyVersion,
    PayType,
    PhilHealthBracket,
    SSSBracket,
)
from app.payroll.routes import (
    _monthly_contribution_snapshot,
    _philhealth_monthly_basic_salary_basis,
)

# --------------------------------------------------------------------------- #
# Helpers / constants
# --------------------------------------------------------------------------- #

API = f"{settings.API_V1_STR}/payroll"


def _dec(value: float | str) -> Decimal:
    """Decimal helper for assertions on values that may arrive as floats."""
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)


def _assert_share_shape(data: dict[str, Any]) -> None:
    assert set(data) == {"employee_share", "employer_share", "total"}
    assert all(isinstance(v, float) for v in data.values())


def test_monthly_contribution_snapshot_uses_each_effective_schedule(
    db: Session,
) -> None:
    philhealth_row = PhilHealthBracket(
        salary_min=Decimal("10000"), salary_max=Decimal("100000"),
        rate=Decimal("5"), employer_share=Decimal("2.5"),
        employee_share=Decimal("2.5"), effective_date=date(2025, 1, 1),
    )
    pagibig_row = PagIBIGBracket(
        salary_min=Decimal("0.01"), salary_max=Decimal("10000"),
        employee_rate=Decimal("2"), employer_rate=Decimal("2"),
        effective_date=date(2024, 2, 1),
    )
    # SSS 2025 is seeded from the published employer schedule in the migration;
    # use it instead of inserting an overlapping test-only row.
    db.add_all([philhealth_row, pagibig_row])
    db.flush()

    snapshot = _monthly_contribution_snapshot(
        session=db,
        sss_monthly_compensation=Decimal("26000"),
        philhealth_basic_salary=Decimal("26000"),
        pagibig_monthly_salary=Decimal("26000"),
        contribution_month=date(2026, 10, 1),
        source_urls=[
            "https://www.sss.gov.ph/pay-contribution/",
            "https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf",
            "https://www.pagibigfund.gov.ph/document/pdf/circulars/provident/HDMF%20Circular%20No.%20274.pdf",
        ],
    )

    assert snapshot["month"] == "2026-10"
    assert _dec(snapshot["schemes"]["sss"]["employee"]) == Decimal("1300")
    assert _dec(snapshot["schemes"]["sss"]["employer"]) == Decimal("2630")
    assert _dec(snapshot["schemes"]["philhealth"]["employee"]) == Decimal("650")
    assert _dec(snapshot["schemes"]["philhealth"]["employer"]) == Decimal("650")
    assert _dec(snapshot["schemes"]["pagibig"]["employee"]) == Decimal("200")
    assert _dec(snapshot["schemes"]["pagibig"]["employer"]) == Decimal("200")
    assert all(
        row["id"] and row["effective_date"]
        for scheme in snapshot["schemes"].values()
        for row in scheme["schedule_rows"]
    )
    for row in (philhealth_row, pagibig_row):
        db.delete(row)
    db.flush()


@pytest.mark.parametrize(
    ("pay_type", "rate", "expected"),
    [
        (PayType.DAILY, "1000.00", "24064.52"),
        (PayType.HOURLY, "125.00", "24064.52"),
    ],
)
def test_philhealth_monthly_basic_salary_converts_time_based_rates_without_attendance(
    db: Session, pay_type: PayType, rate: str, expected: str
) -> None:
    employee = EmployeeRecords(
        employee_code=f"PH-MBS-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="MBS",
        birthdate=date(1990, 1, 1),
        date_hired=date(2020, 1, 1),
    )
    shift = Shift(
        code=f"PH-MBS-{uuid.uuid4().hex[:8]}",
        name="Weekday eight-hour shift",
        start_time="08:00",
        end_time="17:00",
        total_hours_minus_lunch=480,
    )
    db.add_all([employee, shift])
    db.flush()
    salary = EmployeeSalary(
        employee_id=employee.id,
        basic_rate=Decimal(rate),
        effective_date=date(2026, 10, 1),
        pay_type=pay_type,
    )
    db.add_all(
        [
            salary,
            EmployeeShiftAssignment(
                employee_id=employee.id,
                shift_id=shift.id,
                effective_from=date(2026, 10, 1),
            ),
        ]
    )
    policy_version = 980_000 + int(uuid.uuid4().hex[:6], 16)
    policy_before_change = PayrollPolicyVersion(
        version=policy_version,
        effective_from=date(2026, 10, 1),
        effective_to=date(2026, 10, 15),
        policy={"monthly_divisor": "22"},
        confirmed=True,
    )
    policy_after_change = PayrollPolicyVersion(
        version=policy_version + 1,
        effective_from=date(2026, 10, 16),
        effective_to=date(2026, 10, 31),
        policy={"monthly_divisor": "26"},
        confirmed=True,
    )
    db.add_all([policy_before_change, policy_after_change])
    db.flush()

    basis = _philhealth_monthly_basic_salary_basis(
        session=db,
        employee_id=employee.id,
        salaries=[salary],
        contribution_month=date(2026, 10, 1),
        policies=[policy_before_change, policy_after_change],
    )

    assert basis == Decimal(expected)


# Actual response-shape constants verified against routes.py handlers
SSS_KEYS = {"employee_share", "employer_share", "total"}
PHILHEALTH_KEYS = {"employee_share", "employer_share", "total"}
PAGIBIG_KEYS = {"employee_share", "employer_share", "total"}
BIR_KEYS = {"tax_amount"}  # Route returns exactly {"tax_amount": float(...)}
BATCH_CONTRIBUTION_KEYS = {
    "sss_employee", "sss_employer",
    "philhealth_employee", "philhealth_employer",
    "pagibig_employee", "pagibig_employer",
    "taxable_income", "bir",
}

PUBLIC_KEYS = {"id", "salary_min", "salary_max", "effective_date", "is_active", "is_deleted", "rate", "created_at", "updated_at"}
BIR_PUBLIC_KEYS = {
    "id", "period", "bracket_min", "bracket_max", "base_tax", "excess_rate",
    "effective_date", "source_reference", "is_active", "is_deleted", "created_at", "updated_at",
}
PAGIBIG_PUBLIC_KEYS = {"id", "salary_min", "salary_max", "effective_date", "is_active", "is_deleted", "employee_rate", "employer_rate", "created_at", "updated_at"}
SSS_PUBLIC_KEYS = {
    "id", "msc_min", "msc_max", "compensation_min", "compensation_max", "monthly_salary_credit", "employer_ss", "employer_ec", "employer_mpf",
    "employee_ss", "employee_mpf", "effective_date", "is_active", "is_deleted", "created_at", "updated_at",
}
PHILHEALTH_PUBLIC_KEYS = {
    "id", "salary_min", "salary_max", "employer_share", "employee_share", "rate",
    "effective_date", "is_active", "is_deleted", "created_at", "updated_at",
}


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="function")
def sss_brackets(db: Session) -> Generator[list[SSSBracket], None, None]:
    bracket1 = SSSBracket(
        msc_min=2000, msc_max=10000, employer_ss=1000, employer_ec=26,
        compensation_min=2000, compensation_max=10000, monthly_salary_credit=10000,
        employer_mpf=0, employee_ss=500, employee_mpf=0,
        effective_date="2024-01-01", is_active=True,
    )
    bracket2 = SSSBracket(
        msc_min=10001, msc_max=30000, employer_ss=1026, employer_ec=30,
        compensation_min=10001, compensation_max=None, monthly_salary_credit=30000,
        employer_mpf=0, employee_ss=500, employee_mpf=0,
        effective_date="2024-07-01", is_active=True,
    )
    db.add(bracket1)
    db.add(bracket2)
    db.commit()
    yield [bracket1, bracket2]
    db.delete(bracket1)
    db.delete(bracket2)
    db.commit()


@pytest.fixture(scope="function")
def philhealth_brackets(db: Session) -> Generator[list[PhilHealthBracket], None, None]:
    bracket1 = PhilHealthBracket(
        salary_min=10000, salary_max=40000, rate=5.0,
        employer_share=2.5, employee_share=2.5,
        effective_date="2024-01-01", is_active=True,
    )
    bracket2 = PhilHealthBracket(
        salary_min=15000, salary_max=40001, rate=5.0,
        employer_share=2.5, employee_share=2.5,
        effective_date="2024-07-01", is_active=True,
    )
    db.add(bracket1)
    db.add(bracket2)
    db.commit()
    yield [bracket1, bracket2]
    db.delete(bracket1)
    db.delete(bracket2)
    db.commit()


@pytest.fixture(scope="function")
def pagibig_brackets(db: Session) -> Generator[list[PagIBIGBracket], None, None]:
    bracket1 = PagIBIGBracket(
        salary_min=0.01, salary_max=1500, employee_rate=1.0, employer_rate=2.0,
        effective_date="2024-01-01", is_active=True,
    )
    bracket2 = PagIBIGBracket(
        salary_min=1500.01, salary_max=5000, employee_rate=2.0, employer_rate=2.0,
        effective_date="2024-01-01", is_active=True,
    )
    bracket3 = PagIBIGBracket(
        salary_min=0.01, salary_max=1500, employee_rate=1.0, employer_rate=2.0,
        effective_date="2024-02-01", is_active=True,
    )
    bracket4 = PagIBIGBracket(
        salary_min=1500.01, salary_max=10000, employee_rate=2.0, employer_rate=2.0,
        effective_date="2024-02-01", is_active=True,
    )
    rows = [bracket1, bracket2, bracket3, bracket4]
    db.add_all(rows)
    db.commit()
    yield rows
    for row in rows:
        db.delete(row)
    db.commit()


@pytest.fixture(scope="function")
def bir_brackets(db: Session) -> Generator[list[BIRBracket], None, None]:
    monthly_data = [
        (0, 10416.67, 0, 20),
        (10416.68, 20833.33, 2083.33, 25),
        (20833.34, 999999999, 4687.49, 30),
    ]
    brackets: list[BIRBracket] = []
    for br_min, br_max, base_tax, excess_rate in monthly_data:
        b = BIRBracket(
            period="monthly", bracket_min=br_min, bracket_max=br_max,
            base_tax=base_tax, excess_rate=excess_rate,
            effective_date="2024-01-01", is_active=True,
        )
        brackets.append(b)
        db.add(b)
    db.commit()
    yield brackets
    for b in brackets:
        db.delete(b)
    db.commit()


# --------------------------------------------------------------------------- #
# SSS calculations
# --------------------------------------------------------------------------- #

class TestSSSCalculation:

    def test_explicit_monthly_compensation_parameter(self, client: TestClient, superuser_token_headers, sss_brackets):
        response = client.post(
            f"{API}/sss/calculate",
            params={"monthly_compensation": 10000.0, "effective_date": "2024-01-01"},
            headers=superuser_token_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["employee_share"] == 500.0
        assert response.json()["employer_share"] == 1026.0

    def test_sss_rejects_ambiguous_compensation_parameters(self, client: TestClient, superuser_token_headers):
        response = client.post(
            f"{API}/sss/calculate",
            params={"monthly_compensation": 10000.0, "msc": 10000.0},
            headers=superuser_token_headers,
        )
        assert response.status_code == 422
        assert "exactly one" in response.text

    def test_full_range(self, client: TestClient, superuser_token_headers, sss_brackets):
        response = client.post(f"{API}/sss/calculate",
                               params={"msc": 10000.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == SSS_KEYS
        assert all(isinstance(v, float) for v in data.values())
        assert data["employee_share"] == 500.0
        assert data["employer_share"] == 1026.0
        assert data["total"] == 1526.0

    def test_first_bracket_rates_and_upper_bound(self, client: TestClient, superuser_token_headers, sss_brackets):
        response = client.post(f"{API}/sss/calculate",
                               params={"msc": 10000.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == SSS_KEYS
        assert data["employee_share"] == 500.0
        assert data["employer_share"] == 1026.0
        assert data["total"] == 1526.0

    def test_second_bracket_rates(self, client: TestClient, superuser_token_headers, sss_brackets):
        # A salary band from the later effective schedule is selected by compensation.
        response = client.post(f"{API}/sss/calculate",
                               params={"msc": 10001.0, "effective_date": "2024-07-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == SSS_KEYS
        assert data["employee_share"] == 500.0
        assert data["employer_share"] == 1056.0
        assert data["total"] == 1556.0

    def test_uncovered_sss_salary_is_a_configuration_conflict(self, client: TestClient, superuser_token_headers, sss_brackets):
        response = client.post(f"{API}/sss/calculate",
                               params={"msc": 1000.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 409, response.text
        assert "No SSS compensation band covers" in response.text

    def test_above_range_clamps_to_max(self, client: TestClient, superuser_token_headers, sss_brackets):
        response = client.post(f"{API}/sss/calculate",
                               params={"msc": 100000.0, "effective_date": "2024-07-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == SSS_KEYS
        assert data["employee_share"] == 500.0
        assert data["employer_share"] == 1056.0
        assert data["total"] == 1556.0

    def test_latest_effective_date_selects_newest_bracket(self, client: TestClient, superuser_token_headers, sss_brackets):
        # eff=07-01: both brackets qualify, latest (10001-30000) selected.
        # msc=15000 falls within that bracket → emp=500, er=1026+30=1056.
        response = client.post(f"{API}/sss/calculate",
                               params={"msc": 15000.0, "effective_date": "2024-07-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == SSS_KEYS
        assert data["employee_share"] == 500.0
        assert data["employer_share"] == 1056.0
        assert data["total"] == 1556.0

    def test_boundary_row_at_minimum(self, client: TestClient, superuser_token_headers, sss_brackets):
        response = client.post(f"{API}/sss/calculate",
                               params={"msc": 2000.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["employee_share"] == 500.0
        assert data["employer_share"] == 1026.0

    def test_salary_just_below_schedule_is_not_silently_zeroed(self, client: TestClient, superuser_token_headers, sss_brackets):
        response = client.post(f"{API}/sss/calculate",
                               params={"msc": 1999.99, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 409, response.text

    def test_rejects_non_positive_msc(self, client: TestClient, superuser_token_headers, sss_brackets):
        response = client.post(f"{API}/sss/calculate",
                               params={"msc": 0.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["error"]["message"] == "Request validation failed"


# --------------------------------------------------------------------------- #
# PhilHealth calculations
# --------------------------------------------------------------------------- #

class TestPhilHealthCalculation:

    def test_calculate_employee_share(self, client: TestClient, superuser_token_headers, philhealth_brackets):
        response = client.post(f"{API}/philhealth/calculate",
                               params={"salary": 25000.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == PHILHEALTH_KEYS
        assert isinstance(data["employee_share"], float)
        assert isinstance(data["employer_share"], float)
        assert isinstance(data["total"], float)
        # 25000 * 5% / 2 = 625.00
        assert data["employee_share"] == 625.0
        assert data["employer_share"] == 625.0
        assert data["total"] == 1250.0

    def test_full_range(self, client: TestClient, superuser_token_headers, philhealth_brackets):
        response = client.post(f"{API}/philhealth/calculate",
                               params={"salary": 40000.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == PHILHEALTH_KEYS
        assert data["employee_share"] == 1000.0
        assert data["employer_share"] == 1000.0
        assert data["total"] == 2000.0

    def test_below_range_clamps_basis_to_min(self, client: TestClient, superuser_token_headers, philhealth_brackets):
        response = client.post(f"{API}/philhealth/calculate",
                               params={"salary": 9999.99, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == PHILHEALTH_KEYS
        # clamp to 10000: 10000 * 5% / 2 = 250.00
        assert data["employee_share"] == 250.0
        assert data["total"] == 500.0

    def test_above_range_clamps_basis_to_max(self, client: TestClient, superuser_token_headers, philhealth_brackets):
        response = client.post(f"{API}/philhealth/calculate",
                               params={"salary": 50000.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == PHILHEALTH_KEYS
        # clamp to 40000: 40000 * 5% / 2 = 1000.00
        assert data["employee_share"] == 1000.0
        assert data["total"] == 2000.0

    def test_half_even_rounding(self, client: TestClient, superuser_token_headers, philhealth_brackets):
        # salary=40001 > salary_max=40000 → clamp to 40000 → 40000*5%/2 = 1000.0
        response = client.post(f"{API}/philhealth/calculate",
                               params={"salary": 40001.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["employee_share"] == 1000.0
        assert data["total"] == 2000.0

    def test_low_salary_clamps_up(self, client: TestClient, superuser_token_headers, philhealth_brackets):
        response = client.post(f"{API}/philhealth/calculate",
                               params={"salary": 5000.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["employee_share"] == 250.0
        assert data["total"] == 500.0

    def test_high_salary_clamps_down(self, client: TestClient, superuser_token_headers, philhealth_brackets):
        response = client.post(f"{API}/philhealth/calculate",
                               params={"salary": 100000.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["employee_share"] == 1000.0
        assert data["total"] == 2000.0

    def test_latest_bracket_separately(self, client: TestClient, superuser_token_headers, philhealth_brackets):
        # eff=07-01 → latest bracket is 15000-40001 (rate 5%).
        # salary=150000 > 40001 → clamp to 40001 → 40001*5%/2 = 1000.025 → ROUND_HALF_EVEN → 1000.02
        response = client.post(f"{API}/philhealth/calculate",
                               params={"salary": 150000.0, "effective_date": "2024-07-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == PHILHEALTH_KEYS
        assert data["employee_share"] == 1000.02
        assert data["total"] == 2000.04

    def test_rejects_non_positive_salary(self, client: TestClient, superuser_token_headers, philhealth_brackets):
        response = client.post(f"{API}/philhealth/calculate",
                               params={"salary": 0.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["error"]["message"] == "Request validation failed"


# --------------------------------------------------------------------------- #
# Pag-IBIG calculations
# --------------------------------------------------------------------------- #

class TestPagIBIGCalculation:

    def test_calculate_employee_share_high_salary(self, client: TestClient, superuser_token_headers, pagibig_brackets):
        response = client.post(f"{API}/pagibig/calculate",
                               params={"salary": 1800.0, "effective_date": "2024-02-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == PAGIBIG_KEYS
        assert isinstance(data["employee_share"], float)
        assert isinstance(data["employer_share"], float)
        assert isinstance(data["total"], float)
        # Above ₱1,500, employee and employer rates are both 2%.
        assert data["employee_share"] == 36.0
        assert data["employer_share"] == 36.0
        assert data["total"] == 72.0

    def test_calculate_employee_share_very_high_salary(self, client: TestClient, superuser_token_headers, pagibig_brackets):
        response = client.post(f"{API}/pagibig/calculate",
                               params={"salary": 5000.0, "effective_date": "2024-02-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == PAGIBIG_KEYS
        assert data["employee_share"] == 100.0
        assert data["employer_share"] == 100.0
        assert data["total"] == 200.0

    def test_first_bracket_rates_and_upper_bound(self, client: TestClient, superuser_token_headers, pagibig_brackets):
        response = client.post(f"{API}/pagibig/calculate",
                               params={"salary": 1500.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == PAGIBIG_KEYS
        assert data["employee_share"] == 15.0
        assert data["employer_share"] == 30.0
        assert data["total"] == 45.0

        response = client.post(f"{API}/pagibig/calculate",
                               params={"salary": 1000.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == PAGIBIG_KEYS
        assert data["employee_share"] == 10.0
        assert data["employer_share"] == 20.0
        assert data["total"] == 30.0

    def test_low_compensation_uses_employee_one_percent_rate(self, client: TestClient, superuser_token_headers, pagibig_brackets):
        response = client.post(f"{API}/pagibig/calculate",
                               params={"salary": 999.99, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["employee_share"] == 10.0
        assert data["employer_share"] == 20.0
        assert data["total"] == 30.0

    def test_above_max_clamps_basis_to_max(self, client: TestClient, superuser_token_headers, pagibig_brackets):
        response = client.post(f"{API}/pagibig/calculate",
                               params={"salary": 7000.0, "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == PAGIBIG_KEYS
        assert data["employee_share"] == 100.0
        assert data["total"] == 200.0

    def test_latest_effective_date(self, client: TestClient, superuser_token_headers, pagibig_brackets):
        response = client.post(f"{API}/pagibig/calculate",
                               params={"salary": 5000.0, "effective_date": "2024-02-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["employee_share"] == 100.0
        assert data["employer_share"] == 100.0
        assert data["total"] == 200.0

    def test_zero_salary(self, client: TestClient, superuser_token_headers, pagibig_brackets):
        # Route declares salary: Decimal = Query(..., gt=0); salary=0 is a 422 validation error.
        response = client.post(f"{API}/pagibig/calculate",
                               params={"salary": 0.0, "effective_date": "2024-07-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 422, response.text

    def test_boundary_rows(self, client: TestClient, superuser_token_headers, pagibig_brackets):
        for bracket in pagibig_brackets:
            params = {"salary": float(bracket.salary_min),
                      "effective_date": bracket.effective_date.isoformat()}
            response = client.post(f"{API}/pagibig/calculate", params=params,
                                   headers=superuser_token_headers)
            assert response.status_code == 200, response.text
            data = response.json()
            _assert_share_shape(data)
            expected_emp = float(
                (
                    _dec(bracket.salary_min)
                    * _dec(bracket.employee_rate)
                    / Decimal("100")
                ).quantize(Decimal("0.01"))
            )
            assert data["employee_share"] == expected_emp
            expected_er = float(
                (
                    _dec(bracket.salary_min)
                    * _dec(bracket.employer_rate)
                    / Decimal("100")
                ).quantize(Decimal("0.01"))
            )
            assert data["employer_share"] == expected_er

    def test_rejects_non_positive_salary(self, client: TestClient, superuser_token_headers, pagibig_brackets):
        response = client.post(f"{API}/pagibig/calculate",
                               params={"salary": -100.0, "effective_date": "2024-07-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["error"]["message"] == "Request validation failed"


# --------------------------------------------------------------------------- #
# BIR calculations
# --------------------------------------------------------------------------- #

class TestBIRCalculation:

    def test_calculate_initial_bracket(self, client: TestClient, superuser_token_headers, bir_brackets):
        response = client.post(f"{API}/bir/calculate",
                               params={"taxable_income": 10000.0, "period_type": "monthly"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == BIR_KEYS
        assert isinstance(data["tax_amount"], float)
        # b1: span 10416.67-0 = 10416.67; in_b=10000; tax = 0 + (10000*20/100) = 2000.0
        assert data["tax_amount"] == 2000.0

    def test_first_bracket_upper_bound(self, client: TestClient, superuser_token_headers, bir_brackets):
        response = client.post(f"{API}/bir/calculate",
                               params={"taxable_income": 10416.67, "period_type": "monthly"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == BIR_KEYS
        assert data["tax_amount"] == 2083.33

    def test_second_bracket_lower_bound(self, client: TestClient, superuser_token_headers, bir_brackets):
        # The selected bracket contributes its base tax plus excess over its own minimum.
        response = client.post(f"{API}/bir/calculate",
                               params={"taxable_income": 10416.68, "period_type": "monthly"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == BIR_KEYS
        assert data["tax_amount"] == 2083.33

    def test_calculate_mid_range_bracket(self, client: TestClient, superuser_token_headers, bir_brackets):
        # 2083.33 base tax plus the 25% tax on income above 10416.68.
        response = client.post(f"{API}/bir/calculate",
                               params={"taxable_income": 15000.0, "period_type": "monthly"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == BIR_KEYS
        assert data["tax_amount"] == 3229.16

    def test_second_bracket_upper_bound(self, client: TestClient, superuser_token_headers, bir_brackets):
        # The upper endpoint remains in the 25% bracket.
        response = client.post(f"{API}/bir/calculate",
                               params={"taxable_income": 20833.33, "period_type": "monthly"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == BIR_KEYS
        assert data["tax_amount"] == 4687.49

    def test_calculate_high_income_bracket(self, client: TestClient, superuser_token_headers, bir_brackets):
        # 4687.49 base tax plus 30% on income above 20833.34.
        response = client.post(f"{API}/bir/calculate",
                               params={"taxable_income": 33333.33, "period_type": "monthly"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == BIR_KEYS
        assert data["tax_amount"] == 8437.49

    def test_top_unallocated_income_excess_only(self, client: TestClient, superuser_token_headers, bir_brackets):
        # Same income as above (50000), verify top bracket calculation consistency.
        response = client.post(f"{API}/bir/calculate",
                               params={"taxable_income": 50000.0, "period_type": "monthly"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == BIR_KEYS
        assert data["tax_amount"] == 13437.49

    def test_two_brackets_same_rate_no_base_tax(self, client: TestClient, superuser_token_headers, bir_brackets):
        # Adjacent bracket boundary: both produce identical outputs.
        expected = []
        for taxable in [20833.33, 20833.34]:
            response = client.post(f"{API}/bir/calculate",
                                   params={"taxable_income": taxable, "period_type": "monthly"},
                                   headers=superuser_token_headers)
            assert response.status_code == 200, response.text
            data = response.json()
            assert set(data) == BIR_KEYS
            expected.append(data["tax_amount"])
        assert expected[0] == 4687.49
        assert expected[0] == expected[1]

    def test_valid_period_with_no_brackets_is_a_configuration_conflict(self, client: TestClient, superuser_token_headers, bir_brackets):
        # "weekly" is valid but only a monthly schedule is configured. A
        # missing table must never be indistinguishable from a zero-tax result.
        response = client.post(f"{API}/bir/calculate",
                               params={
                                   "taxable_income": 25000.0,
                                   "period_type": "weekly",
                                   "effective_date": "2022-12-31",
                               },
                               headers=superuser_token_headers)
        assert response.status_code == 409, response.text
        assert "No active BIR weekly tax table" in response.text

    def test_rejects_non_positive_taxable_income(self, client: TestClient, superuser_token_headers, bir_brackets):
        response = client.post(f"{API}/bir/calculate",
                               params={"taxable_income": 0.0, "period_type": "monthly"},
                               headers=superuser_token_headers)
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["error"]["message"] == "Request validation failed"

    def test_rejects_malformed_effective_date(self, client: TestClient, superuser_token_headers, bir_brackets):
        response = client.post(
            f"{API}/bir/calculate",
            params={"taxable_income": 25000.0, "period_type": "monthly", "effective_date": "not-a-date"},
            headers=superuser_token_headers,
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["message"] == "Request validation failed"


# --------------------------------------------------------------------------- #
# Batch contribution calculation
# --------------------------------------------------------------------------- #

class TestBatchContributionCalculation:

    def test_sss_selects_matching_row_from_effective_schedule(
        self, db: Session
    ) -> None:
        """All MSC bands on one effective date must be considered together."""
        rows = [
            SSSBracket(
                msc_min=5000, msc_max=10000, employer_ss=1000,
                compensation_min=0, compensation_max=9999.99, monthly_salary_credit=10000,
                employer_ec=10, employer_mpf=0, employee_ss=500,
                employee_mpf=0, effective_date="2025-01-01", is_active=True,
            ),
            SSSBracket(
                msc_min=10001, msc_max=20000, employer_ss=2000,
                compensation_min=10000, compensation_max=19999.99, monthly_salary_credit=20000,
                employer_ec=30, employer_mpf=0, employee_ss=1000,
                employee_mpf=0, effective_date="2025-01-01", is_active=True,
            ),
            SSSBracket(
                msc_min=20001, msc_max=35000, employer_ss=2000,
                compensation_min=20000, compensation_max=None, monthly_salary_credit=35000,
                employer_ec=30, employer_mpf=1500, employee_ss=1000,
                employee_mpf=750, effective_date="2025-01-01", is_active=True,
            ),
        ]
        db.add_all(rows)
        db.commit()
        try:
            from app.payroll.calc import (
                calculate_sss_employee_share,
                calculate_sss_employer_share,
            )

            assert calculate_sss_employee_share(
                db, Decimal("15000"), "2025-02-01"
            ) == Decimal("1000")
            assert calculate_sss_employer_share(
                db, Decimal("15000"), "2025-02-01"
            ) == Decimal("2030")
            assert calculate_sss_employee_share(
                db, Decimal("35000"), "2025-02-01"
            ) == Decimal("1750")
            assert calculate_sss_employer_share(
                db, Decimal("40000"), "2025-02-01"
            ) == Decimal("3530")
        finally:
            for row in rows:
                db.delete(row)
            db.commit()

    def test_pagibig_selects_rate_band_and_caps_monthly_fund_salary(
        self, db: Session, pagibig_brackets: list[PagIBIGBracket]
    ) -> None:
        from app.payroll.calc import (
            calculate_pagibig_employee_share,
            calculate_pagibig_employer_share,
        )

        as_of = "2024-02-01"
        assert calculate_pagibig_employee_share(
            db, Decimal("1500"), as_of
        ) == Decimal("15.00")
        assert calculate_pagibig_employer_share(
            db, Decimal("1500"), as_of
        ) == Decimal("30.00")
        assert calculate_pagibig_employee_share(
            db, Decimal("1500.01"), as_of
        ) == Decimal("30.00")
        assert calculate_pagibig_employee_share(
            db, Decimal("25000"), as_of
        ) == Decimal("200.00")
        assert calculate_pagibig_employer_share(
            db, Decimal("25000"), as_of
        ) == Decimal("200.00")

    def test_calculate_contributions(self, client: TestClient, superuser_token_headers,
                                      sss_brackets, philhealth_brackets, pagibig_brackets,
                                      bir_brackets):
        response = client.post(f"{API}/calculate-contributions/",
                               params={"gross_pay": 25000.0, "period_type": "monthly",
                                       "effective_date": "2024-07-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == {"contributions"}
        c = data["contributions"]
        assert set(c) == BATCH_CONTRIBUTION_KEYS
        assert all(isinstance(v, float) for v in c.values())

        # Exact values computed via real calculator contract:
        assert c["sss_employee"] == 500.0
        assert c["sss_employer"] == 1056.0
        assert c["philhealth_employee"] == 625.0
        assert c["philhealth_employer"] == 625.0
        assert c["pagibig_employee"] == 200.0
        assert c["pagibig_employer"] == 200.0
        assert _dec(c["taxable_income"]) == Decimal("25000.00") - Decimal("500.00") - Decimal("625.00") - Decimal("200.00")
        assert c["taxable_income"] == 23675.0
        # The selected bracket supplies one cumulative base tax plus tax on excess.
        assert c["bir"] == 5539.99

    def test_calculate_contributions_without_effective_date(self, client: TestClient, superuser_token_headers,
                                                             sss_brackets, philhealth_brackets, pagibig_brackets,
                                                             bir_brackets):
        # No effective_date → today → latest applicable effective schedule.
        # SSS 2025: ₱15,000 compensation maps to ₱15,000 MSC; employee=₱750,
        # employer regular SS=₱1,500 plus EC=₱30.
        # PH: 15000 >= min 15000, <= max 40001 → exact → 15000*5%/2 = 375.0
        # PI: 15000 > max 10000 → clamp → 10000*2%=200 for each share.
        response = client.post(f"{API}/calculate-contributions/",
                               params={"gross_pay": 15000.0, "period_type": "monthly"},
                               headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert set(data) == {"contributions"}
        c = data["contributions"]
        assert set(c) == BATCH_CONTRIBUTION_KEYS

        assert c["sss_employee"] == 750.0
        assert c["sss_employer"] == 1530.0
        assert c["philhealth_employee"] == 375.0
        assert c["philhealth_employer"] == 375.0
        assert c["pagibig_employee"] == 200.0
        assert c["pagibig_employer"] == 200.0
        assert _dec(c["taxable_income"]) == Decimal("15000.00") - Decimal("750.00") - Decimal("375.00") - Decimal("200.00")
        assert c["taxable_income"] == 13675.0
        assert c["bir"] == 2897.91

    def test_calculate_contributions_with_incomplete_sss_schedule_fails_closed(self, client: TestClient, superuser_token_headers,
                                                    sss_brackets, philhealth_brackets, pagibig_brackets,
                                                    bir_brackets):
        response = client.post(f"{API}/calculate-contributions/",
                               params={"gross_pay": 1000.0, "period_type": "monthly",
                                       "effective_date": "2024-01-01"},
                               headers=superuser_token_headers)
        assert response.status_code == 409, response.text
        assert "No SSS compensation band covers" in response.text

    def test_rejects_non_positive_gross_pay(self, client: TestClient, superuser_token_headers):
        response = client.post(f"{API}/calculate-contributions/",
                               params={"gross_pay": 0.0, "period_type": "monthly"},
                               headers=superuser_token_headers)
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["error"]["message"] == "Request validation failed"


# --------------------------------------------------------------------------- #
# Bracket list endpoints
# --------------------------------------------------------------------------- #

class TestBracketListEndpoints:

    def test_list_sss_brackets(self, client: TestClient, superuser_token_headers, sss_brackets):
        response = client.get(f"{API}/sss-brackets/",
                              params={"effective_date": "2024-01-01"},
                              headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        brackets = response.json()
        for bracket in brackets:
            assert set(bracket) == SSS_PUBLIC_KEYS
        assert len(brackets) == 1
        b = brackets[0]
        assert str(b["msc_min"]) == "2000.00"
        assert str(b["msc_max"]) == "10000.00"
        assert str(b["employee_ss"]) == "500.00"
        assert str(b["employer_ss"]) == "1000.00"

    def test_list_philhealth_brackets(self, client: TestClient, superuser_token_headers, philhealth_brackets):
        response = client.get(f"{API}/philhealth-brackets/",
                              params={"effective_date": "2024-01-01"},
                              headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        for bracket in response.json():
            assert set(bracket) == PHILHEALTH_PUBLIC_KEYS
        for bracket in response.json():
            assert bracket["rate"] == "5.000"

    def test_list_pagibig_brackets(self, client: TestClient, superuser_token_headers, pagibig_brackets):
        # The list endpoint ignores effective_date (handler declares _effective_date):
        # all non-deleted rows are returned regardless of date.
        response = client.get(f"{API}/pagibig-brackets/",
                              headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        brackets = response.json()
        for bracket in brackets:
            assert set(bracket) == PAGIBIG_PUBLIC_KEYS
        payload = {
            (
                bracket["effective_date"],
                bracket["salary_min"],
                bracket["salary_max"],
                bracket["employee_rate"],
                bracket["employer_rate"],
            )
            for bracket in brackets
        }
        assert payload == {
            ("2024-01-01", "0.01", "1500.00", "1.000", "2.000"),
            ("2024-01-01", "1500.01", "5000.00", "2.000", "2.000"),
            ("2024-02-01", "0.01", "1500.00", "1.000", "2.000"),
            ("2024-02-01", "1500.01", "10000.00", "2.000", "2.000"),
        }

    def test_list_bir_brackets(self, client: TestClient, superuser_token_headers, bir_brackets):
        response = client.get(f"{API}/bir-brackets/",
                              params={"period_type": "monthly", "effective_date": "2024-01-01"},
                              headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        for bracket in response.json():
            assert set(bracket) == BIR_PUBLIC_KEYS
        assert all(b["period"] == "monthly" for b in response.json())

    def test_default_dates_return_all_active(self, client: TestClient, superuser_token_headers, sss_brackets):
        response = client.get(f"{API}/sss-brackets/", headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        brackets = response.json()
        assert len(brackets) == 63
        for b in brackets:
            assert set(b) == SSS_PUBLIC_KEYS
        dates = {b["effective_date"] for b in brackets}
        assert dates == {"2024-01-01", "2024-07-01", "2025-01-01"}
        assert sum(b["effective_date"] == "2025-01-01" for b in brackets) == 61


# --------------------------------------------------------------------------- #
# Health check
# --------------------------------------------------------------------------- #

class TestPayrollApiHealth:

    def test_endpoints_respond(self, client: TestClient, superuser_token_headers,
                               sss_brackets, philhealth_brackets, pagibig_brackets, bir_brackets):
        endpoints = [
            ("GET", f"{API}/sss-brackets/"),
            ("POST", f"{API}/sss/calculate/?msc=5000&effective_date=2024-01-01"),
            ("GET", f"{API}/philhealth-brackets/"),
            ("POST", f"{API}/philhealth/calculate/?salary=30000&effective_date=2024-01-01"),
            ("GET", f"{API}/pagibig-brackets/"),
            ("POST", f"{API}/pagibig/calculate/?salary=1000&effective_date=2024-01-01"),
            ("GET", f"{API}/bir-brackets/?period_type=monthly&effective_date=2024-01-01"),
            ("POST", f"{API}/bir/calculate/?taxable_income=15000&period_type=monthly"),
            ("POST", f"{API}/calculate-contributions/?gross_pay=25000&period_type=monthly&effective_date=2024-07-01"),
        ]
        for method, url in endpoints:
            if method == "GET":
                resp = client.get(url, headers=superuser_token_headers)
            else:
                resp = client.post(url, headers=superuser_token_headers)
            assert resp.status_code == 200, f"{method} {url}: {resp.text}"
            if resp.status_code == 200:
                assert resp.json(), f"{method} {url} returned empty JSON"


class TestCalculatorRequiresAuthentication:
    """The five contribution calculators were public; they now require a valid token."""

    def test_calculate_contributions_requires_auth(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/calculate-contributions/",
            params={"gross_pay": 25000.0, "period_type": "monthly"},
        )
        assert response.status_code == 401, response.text

    def test_sss_calculate_requires_auth(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/sss/calculate",
            params={"msc": 10000.0},
        )
        assert response.status_code == 401, response.text

    def test_philhealth_calculate_requires_auth(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/philhealth/calculate",
            params={"salary": 25000.0},
        )
        assert response.status_code == 401, response.text

    def test_pagibig_calculate_requires_auth(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/pagibig/calculate",
            params={"salary": 25000.0},
        )
        assert response.status_code == 401, response.text

    def test_bir_calculate_requires_auth(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/bir/calculate",
            params={"taxable_income": 25000.0, "period_type": "monthly"},
        )
        assert response.status_code == 401, response.text

    def test_sss_calculate_authenticated_returns_200(
        self, client: TestClient, superuser_token_headers: dict[str, str], sss_brackets: list[SSSBracket]
    ) -> None:
        response = client.post(
            f"{API}/sss/calculate",
            params={"msc": 10000.0, "effective_date": "2024-01-01"},
            headers=superuser_token_headers,
        )
        assert response.status_code == 200, response.text
