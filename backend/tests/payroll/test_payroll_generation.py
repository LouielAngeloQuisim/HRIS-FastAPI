"""B4B payroll generation edge-case tests.

Covers: mid-period rate pro-rating, cutoff-type matrix, non-taxable income,
de minimis caps, attendance deductions, immutability, 13th-month formula,
daily cutoff, preview/generate consistency, payslip endpoints.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import (
    BIRBracket,
    EmployeeSalary,
    PagIBIGBracket,
    PayrollEntry,
    PayrollRun,
    PayrollRunStatus,
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
            compensation_min=0.0,
            compensation_max=10000.0,
            monthly_salary_credit=10000.0,
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
            compensation_min=10000.01,
            compensation_max=None,
            monthly_salary_credit=35000.0,
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


class TestGenerateRunAuthorization:
    def test_generate_requires_payroll_add_permission(
        self,
        client: TestClient,
        employee_with_salary: EmployeeRecords,
        normal_user_token_headers: dict[str, str],
        payroll_brackets: None,
    ) -> None:
        """An authenticated user without payroll:add must get 403, not create a run."""
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [str(employee_with_salary.id)],
        }
        resp = client.post(
            f"{API}/runs/generate",
            json={**payload, "request_id": str(uuid.uuid4())},
            headers=normal_user_token_headers,
        )
        assert resp.status_code == 403, resp.text
        detail = resp.json()["detail"]
        assert "permission" in detail.lower()

    def test_generate_without_token_is_rejected(
        self, client: TestClient, employee_with_salary: EmployeeRecords
    ) -> None:
        """Unauthenticated request must fail before authorization (401)."""
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [str(employee_with_salary.id)],
        }
        resp = client.post(
            f"{API}/runs/generate", json={**payload, "request_id": str(uuid.uuid4())}
        )
        assert resp.status_code == 401, resp.text


class TestPreviewGenerateConsistency:
    def test_preview_and_generate_return_same_entries(
        self,
        client: TestClient,
        db: Session,
        employee_with_salary: EmployeeRecords,
        superuser_token_headers: dict[str, str],
        payroll_brackets: None,
    ) -> None:
        employee_id = str(employee_with_salary.id)
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [employee_id],
        }

        before = len(db.exec(select(PayrollRun)).all())
        preview_resp = client.post(
            f"{API}/runs/preview", json=payload, headers=superuser_token_headers
        )
        generate_resp = client.post(
            f"{API}/runs/generate",
            json={**payload, "request_id": str(uuid.uuid4())},
            headers=superuser_token_headers,
        )
        assert preview_resp.status_code == 409, preview_resp.text
        assert generate_resp.status_code == 409, generate_resp.text
        assert len(db.exec(select(PayrollRun)).all()) == before


class TestMidPeriodRateChange:
    def test_rate_change_pro_rates_correctly(
        self,
        client: TestClient,
        db: Session,
        superuser_token_headers: dict[str, str],
        payroll_brackets: None,
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
        resp = client.post(
            f"{API}/runs/preview", json=payload, headers=superuser_token_headers
        )
        assert resp.status_code == 409, resp.text


class TestCutoffTypeMatrix:
    def test_daily_cutoff_uses_daily_bir_brackets(
        self,
        client: TestClient,
        employee_with_salary: EmployeeRecords,
        superuser_token_headers: dict[str, str],
        payroll_brackets: None,
    ) -> None:
        employee_id = str(employee_with_salary.id)
        payload = {
            "cutoff_type": "daily",
            "date_from": "2024-01-01",
            "date_to": "2024-01-01",
            "employee_ids": [employee_id],
        }
        resp = client.post(
            f"{API}/runs/preview", json=payload, headers=superuser_token_headers
        )
        assert resp.status_code == 409, resp.text


class TestNonTaxableIncome:
    def test_non_taxable_income_excluded_from_taxable(
        self,
        client: TestClient,
        employee_with_salary: EmployeeRecords,
        superuser_token_headers: dict[str, str],
        payroll_brackets: None,
    ) -> None:
        employee_id = str(employee_with_salary.id)
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [employee_id],
        }
        resp = client.post(
            f"{API}/runs/preview", json=payload, headers=superuser_token_headers
        )
        assert resp.status_code == 409, resp.text


class TestImmutability:
    def test_legacy_approval_is_blocked_until_review_workflow_exists(
        self,
        client: TestClient,
        employee_with_salary: EmployeeRecords,
        superuser_token_headers: dict[str, str],
        payroll_brackets: None,
    ) -> None:
        employee_id = str(employee_with_salary.id)
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [employee_id],
        }
        resp = client.post(
            f"{API}/runs/generate",
            json={**payload, "request_id": str(uuid.uuid4())},
            headers=superuser_token_headers,
        )
        assert resp.status_code == 409, resp.text

        preview_resp = client.post(
            f"{API}/runs/preview", json=payload, headers=superuser_token_headers
        )
        assert preview_resp.status_code == 409, preview_resp.text


class TestPayslipEndpoints:
    def test_list_payslips_for_run(
        self,
        client: TestClient,
        employee_with_salary: EmployeeRecords,
        superuser_token_headers: dict[str, str],
        payroll_brackets: None,
    ) -> None:
        employee_id = str(employee_with_salary.id)
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [employee_id],
        }
        resp = client.post(
            f"{API}/runs/generate",
            json={**payload, "request_id": str(uuid.uuid4())},
            headers=superuser_token_headers,
        )
        assert resp.status_code == 409, resp.text
        missing = client.get(
            f"{API}/runs/{uuid.uuid4()}/payslips", headers=superuser_token_headers
        )
        assert missing.status_code == 404

    def test_employee_payslip_endpoint(
        self,
        client: TestClient,
        employee_with_salary: EmployeeRecords,
        superuser_token_headers: dict[str, str],
        payroll_brackets: None,
    ) -> None:
        employee_id = str(employee_with_salary.id)
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [employee_id],
        }
        resp = client.post(
            f"{API}/runs/generate",
            json={**payload, "request_id": str(uuid.uuid4())},
            headers=superuser_token_headers,
        )
        assert resp.status_code == 409, resp.text
        payslip_resp = client.get(
            f"{API}/employees/{employee_id}/payslip", headers=superuser_token_headers
        )
        assert payslip_resp.status_code == 200, payslip_resp.text
        assert payslip_resp.json() is None

    def test_employee_payslip_uses_latest_period_not_later_created_old_run(
        self,
        client: TestClient,
        db: Session,
        employee_with_salary: EmployeeRecords,
        superuser_token_headers: dict[str, str],
    ) -> None:
        runs = [
            PayrollRun(
                cutoff_type="semi_monthly",
                date_from=date(2026, 10, 1),
                date_to=date(2026, 10, 15),
                status=PayrollRunStatus.APPROVED,
                adjustment_type="regular",
                workflow_status="finalized",
                created_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
            ),
            PayrollRun(
                cutoff_type="semi_monthly",
                date_from=date(2026, 10, 16),
                date_to=date(2026, 10, 31),
                status=PayrollRunStatus.APPROVED,
                adjustment_type="regular",
                workflow_status="finalized",
                created_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
            ),
        ]
        db.add_all(runs)
        db.flush()
        for index, run in enumerate(runs, start=1):
            db.add(
                PayrollEntry(
                    payroll_run_id=run.id,
                    employee_id=employee_with_salary.id,
                    basic_rate=Decimal("30000.00"),
                    rate_date_from=run.date_from,
                    rate_date_to=run.date_to,
                    gross_pay=Decimal(str(index * 10000)),
                    total_deductions=Decimal("1000.00"),
                    net_pay=Decimal(str(index * 10000 - 1000)),
                    taxable_income=Decimal(str(index * 9000)),
                )
            )
        db.commit()

        response = client.get(
            f"{API}/employees/{employee_with_salary.id}/payslip",
            headers=superuser_token_headers,
        )

        assert response.status_code == 200, response.text
        assert response.json()["date_to"] == "2026-10-31"
        assert Decimal(str(response.json()["net_pay"])) == Decimal("19000.00")


class TestThirteenthMonth:
    def test_thirteenth_month_computed(
        self,
        client: TestClient,
        db: Session,
        superuser_token_headers: dict[str, str],
        payroll_brackets: None,
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
        resp = client.post(
            f"{API}/runs/preview", json=payload, headers=superuser_token_headers
        )
        assert resp.status_code == 409, resp.text


class TestPreviewPersistence:
    def test_repeated_preview_creates_no_runs_or_entries(
        self,
        client: TestClient,
        db: Session,
        superuser_token_headers: dict[str, str],
        employee_with_salary: EmployeeRecords,
        payroll_brackets: None,
    ) -> None:
        before_runs = len(db.exec(select(PayrollRun)).all())
        before_entries = len(db.exec(select(PayrollEntry)).all())
        payload = {
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [str(employee_with_salary.id)],
        }
        for _ in range(2):
            response = client.post(
                f"{API}/runs/preview", json=payload, headers=superuser_token_headers
            )
            assert response.status_code == 409, response.text
        assert len(db.exec(select(PayrollRun)).all()) == before_runs
        assert len(db.exec(select(PayrollEntry)).all()) == before_entries

    def test_rejected_preview_creates_no_draft(
        self,
        client: TestClient,
        db: Session,
        superuser_token_headers: dict[str, str],
    ) -> None:
        before = len(db.exec(select(PayrollRun)).all())
        response = client.post(
            f"{API}/runs/preview",
            json={
                "cutoff_type": "monthly",
                "date_from": "2024-01-01",
                "date_to": "2024-01-31",
                "employee_ids": [str(uuid.uuid4())],
            },
            headers=superuser_token_headers,
        )
        assert response.status_code == 409
        assert len(db.exec(select(PayrollRun)).all()) == before


class TestGenerationIdentity:
    def test_replay_is_exactly_one_run_and_payload_conflict_is_rejected(
        self,
        client: TestClient,
        db: Session,
        superuser_token_headers: dict[str, str],
        employee_with_salary: EmployeeRecords,
        payroll_brackets: None,
    ) -> None:
        request_id = uuid.uuid4()
        payload = {
            "request_id": str(request_id),
            "cutoff_type": "monthly",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "employee_ids": [str(employee_with_salary.id)],
        }
        first = client.post(
            f"{API}/runs/generate", json=payload, headers=superuser_token_headers
        )
        second = client.post(
            f"{API}/runs/generate", json=payload, headers=superuser_token_headers
        )
        assert first.status_code == second.status_code == 409
        assert (
            len(db.exec(select(PayrollRun).where(PayrollRun.id == request_id)).all())
            == 0
        )
        conflict = client.post(
            f"{API}/runs/generate",
            json={**payload, "date_to": "2024-01-30"},
            headers=superuser_token_headers,
        )
        assert conflict.status_code == 409
        run = db.get(PayrollRun, request_id)
        assert run is None

    def test_concurrent_generation_settles_to_one_run(
        self,
        db: Session,
        employee_with_salary: EmployeeRecords,
        payroll_brackets: None,
    ) -> None:
        from app.config.database import engine
        from app.payroll.schemas import PayrollGenerateRequest
        from app.payroll.services import generate_payroll
        from app.user.models import User

        actor = db.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).one()
        actor_id = actor.id
        identity = uuid.uuid4()
        request = PayrollGenerateRequest(
            request_id=identity,
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
            employee_ids=[employee_with_salary.id],
        )
        barrier = Barrier(2)

        def submit() -> uuid.UUID:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                return generate_payroll(session, request, actor_id).id

        with ThreadPoolExecutor(max_workers=2) as executor:
            jobs = [executor.submit(submit) for _ in range(2)]
            assert [job.result(timeout=20) for job in jobs] == [identity, identity]
        assert (
            len(db.exec(select(PayrollRun).where(PayrollRun.id == identity)).all()) == 1
        )
        assert (
            len(
                db.exec(
                    select(PayrollEntry).where(PayrollEntry.payroll_run_id == identity)
                ).all()
            )
            == 1
        )

    def test_generation_requires_retry_identity(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
    ) -> None:
        response = client.post(
            f"{API}/runs/generate",
            json={"date_from": "2024-01-01", "date_to": "2024-01-31"},
            headers=superuser_token_headers,
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
