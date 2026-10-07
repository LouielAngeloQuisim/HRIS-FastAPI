"""The attendance payroll preparation route persists blocked, auditable drafts."""

import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import PayrollPayGroup, PayrollPolicyVersion
from app.payroll.payroll_tables import PayrollRun

API = f"{settings.API_V1_STR}/payroll"


def test_prepare_creates_replayable_draft_and_keeps_finalization_blocked(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    employee = EmployeeRecords(
        employee_code=f"DRAFT-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Payroll",
        birthdate=date(1990, 1, 1),
    )
    group = PayrollPayGroup(
        code=f"QA-{uuid.uuid4().hex[:8]}",
        name="QA monthly",
        cadence="monthly",
        weekend_rule="next_business_day",
    )
    db.add(employee)
    db.add(group)
    db.flush()
    policy = PayrollPolicyVersion(
        version=900_000 + int(uuid.uuid4().hex[:6], 16),
        effective_from=date(2026, 9, 1),
        effective_to=None,
        policy={"timezone": "Asia/Manila"},
        confirmed=True,
    )
    db.add(policy)
    db.commit()

    payload = {
        "pay_group_id": str(group.id),
        "date_from": "2026-09-01",
        "date_to": "2026-09-30",
    }
    first = client.post(
        f"{API}/runs/prepare-attendance-draft",
        json=payload,
        headers=superuser_token_headers,
    )
    assert first.status_code == 201, first.text
    data = first.json()
    assert data["workflow_status"] == "draft"
    entry = next(row for row in data["entries"] if row["employee_id"] == str(employee.id))
    assert entry["review_state"] == "blocked"
    assert any(
        blocker["code"] == "statutory_calculation_unavailable"
        for blocker in entry["blockers"]
    )
    assert entry["input_fingerprint"]

    replay = client.post(
        f"{API}/runs/prepare-attendance-draft",
        json=payload,
        headers=superuser_token_headers,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == data["id"]
    assert len(db.exec(select(PayrollRun).where(PayrollRun.pay_group_id == group.id)).all()) == 1

    review = client.post(
        f"{API}/runs/{data['id']}/start-review", headers=superuser_token_headers
    )
    assert review.status_code == 409
