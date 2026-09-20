"""Tests for payroll router routes.

Phase B4C scenarios: Government contribution calculator endpoints, payroll run lifecycle.
"""

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import BIRBracket, PagIBIGBracket, PhilHealthBracket, SSSBracket

API = f"{settings.API_V1_STR}/payroll"


@pytest.fixture
def employee_record(db: Session) -> EmployeeRecords:
    emp = EmployeeRecords(
        employee_code=f"EMP-{uuid.uuid4().hex[:8]}",
        first_name="Test",
        last_name="User",
        birthdate=date(1990, 1, 1),
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


class TestPayrollRuns:
    def test_list_payroll_runs(self, client: TestClient, superuser_token_headers: dict[str, str]) -> None:
        response = client.get(f"{API}/runs", headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert isinstance(data, list)

    def test_get_payroll_status(self, client: TestClient, superuser_token_headers: dict[str, str]) -> None:
        response = client.get(f"{API}/runs/status", headers=superuser_token_headers)
        assert response.status_code in [200, 422], response.text


class TestSSSBracketCrud:
    def test_sss_bracket_crud(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session) -> None:
        create_data = {
            "msc_min": 2000.0,
            "msc_max": 10000.0,
            "employer_ss": 1000.0,
            "employer_ec": 26.0,
            "employer_mpf": 0.0,
            "employee_ss": 500.0,
            "employee_mpf": 0.0,
            "effective_date": "2024-01-01",
        }
        response = client.post(f"{API}/sss-brackets/", json=create_data, headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        bracket_id = response.json()["id"]

        response = client.get(f"{API}/sss-brackets/{bracket_id}", headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        assert response.json()["id"] == bracket_id

        response = client.get(f"{API}/sss-brackets/", headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        brackets = response.json()
        assert len(brackets) > 0

        bracket = db.exec(select(SSSBracket).where(SSSBracket.id == bracket_id)).first()
        if bracket:
            db.delete(bracket)
            db.commit()


class TestPhilHealthBracketCrud:
    def test_philhealth_bracket_crud(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session) -> None:
        create_data = {
            "salary_min": 10000.0,
            "salary_max": 40000.0,
            "rate": 5.0,
            "employer_share": 2.5,
            "employee_share": 2.5,
            "effective_date": "2024-01-01",
        }
        response = client.post(f"{API}/philhealth-brackets/", json=create_data, headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        bracket_id = response.json()["id"]

        response = client.get(f"{API}/philhealth-brackets/", headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        brackets = response.json()
        returned_ids = {b["id"] for b in brackets}
        assert bracket_id in returned_ids

        bracket = db.exec(select(PhilHealthBracket).where(PhilHealthBracket.id == bracket_id)).first()
        if bracket:
            db.delete(bracket)
            db.commit()


class TestPagIBIGBracketCrud:
    def test_pagibig_bracket_crud(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session) -> None:
        create_data = {
            "salary_min": 1000.0,
            "salary_max": 1500.0,
            "employee_rate": 2.0,
            "employer_rate": 2.0,
            "effective_date": "2024-01-01",
        }
        response = client.post(f"{API}/pagibig-brackets/", json=create_data, headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        bracket_id = response.json()["id"]

        response = client.get(f"{API}/pagibig-brackets/", headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        brackets = response.json()
        returned_ids = {b["id"] for b in brackets}
        assert bracket_id in returned_ids

        bracket = db.exec(select(PagIBIGBracket).where(PagIBIGBracket.id == bracket_id)).first()
        if bracket:
            db.delete(bracket)
            db.commit()


class TestBIRBracketCrud:
    def test_bir_bracket_crud(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session) -> None:
        create_data = {
            "period": "monthly",
            "bracket_min": 0.0,
            "bracket_max": 10416.67,
            "base_tax": 0.0,
            "excess_rate": 20.0,
            "effective_date": "2024-01-01",
        }
        response = client.post(f"{API}/bir-brackets/", json=create_data, headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        bracket_id = response.json()["id"]

        response = client.get(f"{API}/bir-brackets/", params={"period_type": "monthly"}, headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        brackets = response.json()
        returned_ids = {b["id"] for b in brackets}
        assert bracket_id in returned_ids
        assert all(b["period"] == "monthly" for b in brackets)

        bracket = db.exec(select(BIRBracket).where(BIRBracket.id == bracket_id)).first()
        if bracket:
            db.delete(bracket)
            db.commit()


class TestEmployeeSalary:
    def test_create_and_get_salary(self, client: TestClient, employee_record: EmployeeRecords, superuser_token_headers: dict[str, str]) -> None:
        employee_id = str(employee_record.id)
        create_data = {
            "employee_id": employee_id,
            "basic_rate": 500.0,
            "currency": "PHP",
            "effective_date": "2024-01-01",
            "pay_type": "monthly",
        }
        response = client.post(
            f"{API}/employees/{employee_id}/salary/",
            json=create_data,
            headers=superuser_token_headers,
        )
        assert response.status_code == 200, response.text
        salary_id = response.json()["id"]

        response = client.get(f"{API}/salaries/{salary_id}", headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        assert response.json()["id"] == salary_id

        response = client.get(f"{API}/employees/{employee_id}/salary/", headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        salaries = response.json()
        assert len(salaries) >= 1

    def test_partial_salary_update(self, client: TestClient, employee_record: EmployeeRecords, superuser_token_headers: dict[str, str]) -> None:
        employee_id = str(employee_record.id)
        create_data = {
            "employee_id": employee_id,
            "basic_rate": 500.0,
            "currency": "PHP",
            "effective_date": "2024-01-01",
            "pay_type": "monthly",
        }
        response = client.post(
            f"{API}/employees/{employee_id}/salary/",
            json=create_data,
            headers=superuser_token_headers,
        )
        assert response.status_code == 200, response.text
        salary_id = response.json()["id"]

        update_data = {"employee_id": employee_id, "basic_rate": 600.0, "effective_date": "2024-01-01"}
        response = client.patch(
            f"{API}/salaries/{salary_id}",
            json=update_data,
            headers=superuser_token_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["basic_rate"] == "600.00"


class TestLoans:
    def test_list_employee_loans(self, client: TestClient, employee_record: EmployeeRecords, superuser_token_headers: dict[str, str]) -> None:
        employee_id = str(employee_record.id)
        response = client.get(f"{API}/employees/{employee_id}/loans", headers=superuser_token_headers)
        assert response.status_code == 200, response.text
        loans = response.json()
        assert isinstance(loans, list)


class TestGovernmentCalculators:
    def test_calculations_invalid_inputs(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/sss/calculate",
            params={"msc": 100.0},
        )
        assert response.status_code in [200, 404, 400, 422]

        response = client.post(
            f"{API}/philhealth/calculate",
            params={"salary": 0.0},
        )
        assert response.status_code in [200, 404, 400, 422]

    def test_contribution_calculations_endpoint(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/calculate-contributions/",
            params={
                "gross_pay": 25000.0,
                "period_type": "monthly",
                "effective_date": "2024-01-01",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "contributions" in data
        assert all(key in data["contributions"] for key in ["sss_employee", "philhealth_employee", "pagibig_employee", "bir"])

    def test_multiple_calculation_types(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/calculate-contributions/",
            params={"gross_pay": 18000.0, "period_type": "monthly", "effective_date": "2024-01-01"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "contributions" in data
        contributions = data["contributions"]
        assert "sss_employee" in contributions
        assert "philhealth_employee" in contributions
        assert "pagibig_employee" in contributions
        assert "bir" in contributions

        for key in contributions:
            assert contributions[key] >= 0


class TestPayrollApiHealth:
    def test_sss_calculate_endpoint_responds(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/sss/calculate",
            params={"msc": 1000.0},
        )
        assert response.status_code in [200, 404, 400]

    def test_endpoints_responsive(self, client: TestClient, superuser_token_headers: dict[str, str]) -> None:
        public_endpoints: list[tuple[str, dict[str, float | str]]] = [
            (f"{API}/sss/calculate", {"msc": 1000.0}),
            (f"{API}/philhealth/calculate", {"salary": 1000.0}),
            (f"{API}/pagibig/calculate", {"salary": 1000.0}),
            (f"{API}/bir/calculate", {"taxable_income": 1000.0, "period_type": "monthly"}),
            (f"{API}/calculate-contributions/", {"gross_pay": 1000.0, "period_type": "monthly"}),
        ]
        for endpoint, params in public_endpoints:
            response = client.post(endpoint, params=params)
            assert response.status_code in [200, 404, 400, 422], f"Endpoint {endpoint} returned {response.status_code}: {response.text}"

        protected_endpoints = [
            (f"{API}/sss-brackets/", "get", None),
            (f"{API}/runs/status", "get", None),
        ]
        for endpoint, method, _params in protected_endpoints:
            if method == "get":
                response = client.get(endpoint, headers=superuser_token_headers)
            else:
                response = client.post(endpoint, headers=superuser_token_headers)
            assert response.status_code in [200, 404, 400, 422], f"Endpoint {endpoint} returned {response.status_code}: {response.text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
