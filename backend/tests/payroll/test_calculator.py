"""Tests for government contribution calculator endpoints.

Phase B4C scenarios: Branch boundary verification, official examples, edge case combinations.
"""

import uuid
from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.payroll.models import BIRBracket, PagIBIGBracket, PhilHealthBracket, SSSBracket

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
            msc_max=30000.0,
            employer_ss=1000.0,
            employer_ec=26.0,
            employer_mpf=0.0,
            employee_ss=500.0,
            employee_mpf=0.0,
            effective_date=date(2024, 7, 1),
        ),
    ]
    for bracket in brackets:
        db.add(bracket)
    db.commit()
    for bracket in brackets:
        db.refresh(bracket)
    yield brackets
    for bracket in brackets:
        db.delete(bracket)
    db.commit()


@pytest.fixture
def philhealth_brackets(db: Session) -> Generator[list[PhilHealthBracket], None, None]:
    brackets = [
        PhilHealthBracket(
            id=uuid.uuid4(),
            salary_min=10000.0,
            salary_max=40000.0,
            rate=5.0,
            employer_share=2.5,
            employee_share=2.5,
            effective_date=date(2024, 1, 1),
        ),
        PhilHealthBracket(
            id=uuid.uuid4(),
            salary_min=40001.0,
            salary_max=100000.0,
            rate=5.0,
            employer_share=2.5,
            employee_share=2.5,
            effective_date=date(2024, 7, 1),
        ),
    ]
    for bracket in brackets:
        db.add(bracket)
    db.commit()
    for bracket in brackets:
        db.refresh(bracket)
    yield brackets
    for bracket in brackets:
        db.delete(bracket)
    db.commit()


@pytest.fixture
def pagibig_brackets(db: Session) -> Generator[list[PagIBIGBracket], None, None]:
    brackets = [
        PagIBIGBracket(
            id=uuid.uuid4(),
            salary_min=1000.0,
            salary_max=1500.0,
            employee_rate=2.0,
            employer_rate=2.0,
            effective_date=date(2024, 1, 1),
        ),
        PagIBIGBracket(
            id=uuid.uuid4(),
            salary_min=1501.0,
            salary_max=10000.0,
            employee_rate=1.0,
            employer_rate=2.0,
            effective_date=date(2024, 7, 1),
        ),
    ]
    for bracket in brackets:
        db.add(bracket)
    db.commit()
    for bracket in brackets:
        db.refresh(bracket)
    yield brackets
    for bracket in brackets:
        db.delete(bracket)
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
    ]
    for bracket in brackets:
        db.add(bracket)
    db.commit()
    for bracket in brackets:
        db.refresh(bracket)
    yield brackets
    for bracket in brackets:
        db.delete(bracket)
    db.commit()


class TestSSSCalculation:
    def test_calculate_employee_share(self, client: TestClient, sss_brackets: list[SSSBracket]) -> None:
        response = client.post(
            f"{API}/sss/calculate",
            params={"msc": 10000.0, "effective_date": "2024-01-01"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["employee_share"] == pytest.approx(500.0, abs=0.01)
        assert data["employer_share"] == pytest.approx(1026.0, abs=0.01)
        assert data["total"] == pytest.approx(1526.0, abs=0.01)


class TestPhilHealthCalculation:
    def test_calculate_employee_share(self, client: TestClient, philhealth_brackets: list[PhilHealthBracket]) -> None:
        response = client.post(
            f"{API}/philhealth/calculate",
            params={"salary": 25000.0, "effective_date": "2024-01-01"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["employee_share"] == pytest.approx(625.0, abs=0.01)
        assert data["total"] == pytest.approx(1250.0, abs=0.01)


class TestPagIBIGCalculation:
    def test_calculate_employee_share_high_salary(self, client: TestClient, pagibig_brackets: list[PagIBIGBracket]) -> None:
        response = client.post(
            f"{API}/pagibig/calculate",
            params={"salary": 1800.0, "effective_date": "2024-07-01"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["employee_share"] == pytest.approx(18.0, abs=0.01)
        assert data["employer_share"] == pytest.approx(36.0, abs=0.01)
        assert data["total"] == pytest.approx(54.0, abs=0.01)

    def test_calculate_employee_share_very_high_salary(self, client: TestClient, pagibig_brackets: list[PagIBIGBracket]) -> None:
        response = client.post(
            f"{API}/pagibig/calculate",
            params={"salary": 5000.0, "effective_date": "2024-07-01"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["employee_share"] == pytest.approx(50.0, abs=0.01)
        assert data["employer_share"] == pytest.approx(100.0, abs=0.01)


class TestBIRCalculation:
    def test_calculate_initial_bracket(self, client: TestClient, bir_brackets: list[BIRBracket]) -> None:
        response = client.post(
            f"{API}/bir/calculate",
            params={"taxable_income": 10000.0, "period_type": "monthly"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["tax_amount"] == pytest.approx(2000.0, abs=0.01)

    def test_calculate_mid_range_bracket(self, client: TestClient, bir_brackets: list[BIRBracket]) -> None:
        response = client.post(
            f"{API}/bir/calculate",
            params={"taxable_income": 15000.0, "period_type": "monthly"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        expected_tax = 2083.33 + (15000.0 - 10416.68) * 0.25
        assert data["tax_amount"] == pytest.approx(expected_tax, abs=0.02)

    def test_calculate_high_income_bracket(self, client: TestClient, bir_brackets: list[BIRBracket]) -> None:
        response = client.post(
            f"{API}/bir/calculate",
            params={"taxable_income": 30000.0, "period_type": "monthly"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        expected_tax = 2083.33 + 10416.65 * 0.25 + (2083.33 + (30000.0 - 20833.34) * 0.30)
        assert data["tax_amount"] == pytest.approx(expected_tax, abs=0.02)


class TestBatchContributionCalculation:
    def test_calculate_contributions(
        self, client: TestClient, sss_brackets: list[SSSBracket], philhealth_brackets: list[PhilHealthBracket], pagibig_brackets: list[PagIBIGBracket]
    ) -> None:
        response = client.post(
            f"{API}/calculate-contributions/",
            params={"gross_pay": 25000.0, "period_type": "monthly", "effective_date": "2024-01-01"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "contributions" in data
        contributions = data["contributions"]
        assert contributions["sss_employee"] == pytest.approx(500.0, abs=0.01)
        assert contributions["philhealth_employee"] == pytest.approx(625.0, abs=0.01)
        assert contributions["pagibig_employee"] == pytest.approx(30.0, abs=0.01)

    def test_calculate_contributions_without_effective_date(
        self, client: TestClient, sss_brackets: list[SSSBracket], philhealth_brackets: list[PhilHealthBracket], pagibig_brackets: list[PagIBIGBracket]
    ) -> None:
        response = client.post(
            f"{API}/calculate-contributions/",
            params={"gross_pay": 15000.0, "period_type": "monthly"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "contributions" in data
        contributions = data["contributions"]
        assert contributions["sss_employee"] == pytest.approx(500.0, abs=0.01)


class TestBracketListEndpoints:
    def test_list_sss_brackets(self, client: TestClient, superuser_token_headers: dict[str, str], sss_brackets: list[SSSBracket]) -> None:
        response = client.get(
            f"{API}/sss-brackets/",
            params={"effective_date": "2024-01-01"},
            headers=superuser_token_headers,
        )
        assert response.status_code == 200, response.text
        brackets = response.json()
        returned_ids = {b["id"] for b in brackets}
        matching = [b for b in sss_brackets if b.effective_date == date(2024, 1, 1)]
        assert len(matching) == 1
        assert str(matching[0].id) in returned_ids

    def test_list_philhealth_brackets(self, client: TestClient, superuser_token_headers: dict[str, str], philhealth_brackets: list[PhilHealthBracket]) -> None:
        response = client.get(
            f"{API}/philhealth-brackets/",
            params={"effective_date": "2024-07-01"},
            headers=superuser_token_headers,
        )
        assert response.status_code == 200, response.text
        brackets = response.json()
        returned_ids = {b["id"] for b in brackets}
        matching = [b for b in philhealth_brackets if b.effective_date == date(2024, 7, 1)]
        assert len(matching) == 1
        assert str(matching[0].id) in returned_ids

    def test_list_pagibig_brackets(self, client: TestClient, superuser_token_headers: dict[str, str], pagibig_brackets: list[PagIBIGBracket]) -> None:
        response = client.get(
            f"{API}/pagibig-brackets/",
            headers=superuser_token_headers,
        )
        assert response.status_code == 200, response.text
        brackets = response.json()
        returned_ids = {b["id"] for b in brackets}
        for bracket in pagibig_brackets:
            assert str(bracket.id) in returned_ids

    def test_list_bir_brackets(self, client: TestClient, superuser_token_headers: dict[str, str], bir_brackets: list[BIRBracket]) -> None:
        response = client.get(
            f"{API}/bir-brackets/",
            params={"period_type": "monthly"},
            headers=superuser_token_headers,
        )
        assert response.status_code == 200, response.text
        brackets = response.json()
        returned_ids = {b["id"] for b in brackets}
        for bracket in bir_brackets:
            assert str(bracket.id) in returned_ids
        assert all(b["period"] == "monthly" for b in brackets)


class TestPayrollApiHealth:
    def test_sss_calculate_endpoint_responds(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/sss/calculate",
            params={"msc": 1000.0},
        )
        assert response.status_code in [200, 404, 400]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
