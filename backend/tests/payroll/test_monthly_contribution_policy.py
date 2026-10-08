"""Contribution timing must be explicit and prevent duplicate monthly collection."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.config.settings import settings
from app.payroll.models import (
    BIRBracket,
    PagIBIGBracket,
    PayrollPolicyVersion,
    PhilHealthBracket,
    SSSBracket,
)

API = f"{settings.API_V1_STR}/payroll"


def _policy(frequency: str, collection_period: str) -> dict[str, object]:
    return {
        "timezone": "Asia/Manila",
        "monthly_divisor": "22",
        "daily_partial_work": "pro_rated",
        "monthly_partial_work": "deduct_after_grace",
        "monthly_salary_proration": "scheduled_workday_fraction",
        "monthly_holiday_pay_divisor": "22",
        "paid_leave": False,
        "paid_holidays": False,
        "break_minutes": 60,
        "grace_minutes": 0,
        "overtime_rule": {"multiplier": "1.25"},
        "premium_rules": {"enabled": False},
        "allowance_tax_treatment": {"default": "taxable"},
        "rounding_mode": "half_up",
        "contribution_collection": {
            "frequency": frequency,
            "collection_period": collection_period,
        },
        "statutory_sources_reviewed": [
            "https://www.bir.gov.ph/",
            "https://www.sss.gov.ph/",
            "https://www.philhealth.gov.ph/",
            "https://www.pagibigfund.gov.ph/",
        ],
    }


def test_policy_confirmation_requires_supported_monthly_partial_work_rule(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    created_ids: list[UUID] = []
    for index, rule in enumerate((None, "deduct_by_shift"), start=1):
        payload = _policy("once_monthly", "last_period")
        payload["monthly_partial_work"] = rule
        created = client.post(
            f"{API}/policies",
            json={"effective_from": f"2100-0{index}-01", "policy": payload},
            headers=superuser_token_headers,
        )
        assert created.status_code == 201, created.text
        created_ids.append(UUID(created.json()["id"]))
        confirmed = client.post(
            f"{API}/policies/{created.json()['id']}/confirm",
            headers=superuser_token_headers,
        )
        assert confirmed.status_code == 422
        detail = str(confirmed.json()["detail"])
        assert "monthly_partial_work" in detail
    for policy_id in created_ids:
        policy = db.get(PayrollPolicyVersion, policy_id)
        assert policy is not None
        db.delete(policy)
    db.commit()


def test_policy_confirmation_rejects_unsupported_fixed_allowance_rule(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    payload = _policy("once_monthly", "last_period")
    payload["allowance_tax_treatment"] = {
        "fixed_recurring": "non_taxable",
        "proration": "calendar_days",
        "absence": "not_deducted",
    }
    created = client.post(
        f"{API}/policies",
        json={"effective_from": "2100-03-01", "policy": payload},
        headers=superuser_token_headers,
    )
    assert created.status_code == 201, created.text
    policy_id = UUID(created.json()["id"])
    try:
        rejected = client.post(
            f"{API}/policies/{policy_id}/confirm",
            headers=superuser_token_headers,
        )
        assert rejected.status_code == 422
        detail = str(rejected.json()["detail"])
        assert "Fixed recurring allowance policy is unsupported" in detail
        assert "fixed_recurring" in detail
        assert "taxable" in detail
        assert "calendar_days" in detail
        assert "not_deducted" in detail
    finally:
        row = db.get(PayrollPolicyVersion, policy_id)
        if row is not None:
            db.delete(row)
            db.commit()


def test_policy_confirmation_rejects_unknown_monthly_salary_proration(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    payload = _policy("once_monthly", "last_period")
    payload["monthly_salary_proration"] = "guess_from_attendance"
    created = client.post(
        f"{API}/policies",
        json={"effective_from": "2101-01-01", "policy": payload},
        headers=superuser_token_headers,
    )
    assert created.status_code == 201, created.text
    rejected = client.post(
        f"{API}/policies/{created.json()['id']}/confirm",
        headers=superuser_token_headers,
    )
    assert rejected.status_code == 422
    assert "monthly_salary_proration" in rejected.json()["detail"]
    row = db.get(PayrollPolicyVersion, UUID(created.json()["id"]))
    assert row is not None
    db.delete(row)
    db.commit()


def test_policy_confirmation_requires_a_monthly_holiday_divisor(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    payload = _policy("once_monthly", "last_period")
    payload["monthly_holiday_pay_divisor"] = None
    created = client.post(
        f"{API}/policies",
        json={"effective_from": "2102-01-01", "policy": payload},
        headers=superuser_token_headers,
    )
    assert created.status_code == 201, created.text
    rejected = client.post(
        f"{API}/policies/{created.json()['id']}/confirm",
        headers=superuser_token_headers,
    )
    assert rejected.status_code == 422
    assert "monthly_holiday_pay_divisor" in rejected.json()["detail"]
    row = db.get(PayrollPolicyVersion, UUID(created.json()["id"]))
    assert row is not None
    db.delete(row)
    db.commit()


def test_policy_confirmation_requires_once_monthly_final_period_collection(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    created = client.post(
        f"{API}/policies",
        json={"effective_from": "2100-01-01", "policy": _policy("per_run", "each_period")},
        headers=superuser_token_headers,
    )
    assert created.status_code == 201, created.text
    rejected = client.post(
        f"{API}/policies/{created.json()['id']}/confirm",
        headers=superuser_token_headers,
    )
    assert rejected.status_code == 422
    assert "once per calendar month" in rejected.json()["detail"]

    valid = client.post(
        f"{API}/policies",
        json={
            "effective_from": "2100-02-01",
            "policy": _policy("once_monthly", "last_period"),
        },
        headers=superuser_token_headers,
    )
    assert valid.status_code == 201, valid.text
    effective_date = date(2099, 1, 1)
    schedule_rows = [
        SSSBracket(
            msc_min=0,
            msc_max=19999.99,
            compensation_min=0,
            compensation_max=19999.99,
            monthly_salary_credit=20000,
            employer_ss=0,
            employer_ec=0,
            employer_mpf=0,
            employee_ss=0,
            employee_mpf=0,
            effective_date=effective_date,
        ),
        SSSBracket(
            msc_min=20000,
            msc_max=35000,
            compensation_min=20000,
            compensation_max=None,
            monthly_salary_credit=35000,
            employer_ss=0,
            employer_ec=0,
            employer_mpf=0,
            employee_ss=0,
            employee_mpf=0,
            effective_date=effective_date,
        ),
        PhilHealthBracket(
            salary_min=10000,
            salary_max=100000,
            rate=5,
            employer_share=2.5,
            employee_share=2.5,
            effective_date=effective_date,
        ),
        PagIBIGBracket(
            salary_min=0.01,
            salary_max=1500,
            employee_rate=1,
            employer_rate=2,
            effective_date=effective_date,
        ),
        PagIBIGBracket(
            salary_min=1500.01,
            salary_max=10000,
            employee_rate=2,
            employer_rate=2,
            effective_date=effective_date,
        ),
    ]
    for period in ("daily", "weekly", "semi_monthly", "monthly"):
        schedule_rows.extend(
            [
                BIRBracket(
                    period=period,
                    bracket_min=0,
                    bracket_max=1000,
                    base_tax=0,
                    excess_rate=0,
                    effective_date=effective_date,
                ),
                BIRBracket(
                    period=period,
                    bracket_min=1000.02 if period == "monthly" else 1000.01,
                    bracket_max=None,
                    base_tax=0,
                    excess_rate=1,
                    effective_date=effective_date,
                ),
            ]
        )
    db.add_all(schedule_rows)
    db.commit()
    gap_result = client.post(
        f"{API}/policies/{valid.json()['id']}/confirm",
        headers=superuser_token_headers,
    )
    assert gap_result.status_code == 422
    assert "BIR monthly tax table contains a gap" in str(
        gap_result.json()["detail"]
    )
    monthly_upper_band = next(
        row
        for row in schedule_rows
        if isinstance(row, BIRBracket)
        and getattr(row.period, "value", row.period) == "monthly"
        and row.bracket_min > 1000
    )
    monthly_upper_band.bracket_min = Decimal("1000.01")
    db.add(monthly_upper_band)
    db.commit()
    confirmed = client.post(
        f"{API}/policies/{valid.json()['id']}/confirm",
        headers=superuser_token_headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["confirmed"] is True
    db.exec(
        delete(PayrollPolicyVersion).where(
            PayrollPolicyVersion.id.in_([created.json()["id"], valid.json()["id"]])
        )
    )
    for schedule_row in schedule_rows:
        db.delete(schedule_row)
    db.commit()
    assert db.exec(
        select(SSSBracket).where(
            SSSBracket.effective_date == date(2025, 1, 1),
            SSSBracket.is_active.is_(True),
            SSSBracket.is_deleted.is_(False),
        )
    ).first() is not None
    assert db.exec(
        select(BIRBracket).where(
            BIRBracket.effective_date == date(2023, 1, 1),
            BIRBracket.period == "semi_monthly",
            BIRBracket.is_active.is_(True),
            BIRBracket.is_deleted.is_(False),
        )
    ).first() is not None
