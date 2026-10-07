"""Contribution timing must be explicit and prevent duplicate monthly collection."""

from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.config.settings import settings
from app.payroll.models import PayrollPolicyVersion

API = f"{settings.API_V1_STR}/payroll"


def _policy(frequency: str, collection_period: str) -> dict[str, object]:
    return {
        "timezone": "Asia/Manila",
        "monthly_divisor": "22",
        "daily_partial_work": "pro_rated",
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
    db.commit()
