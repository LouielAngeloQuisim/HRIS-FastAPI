"""Guard legacy payroll runs from entering the new immutable review flow."""

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config.settings import settings
from app.payroll.models import PayrollRun, PayrollRunStatus
from app.user.models import User

API = f"{settings.API_V1_STR}/payroll"


def _legacy_run(db: Session) -> PayrollRun:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    run = PayrollRun(
        cutoff_type="monthly",
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 30),
        status=PayrollRunStatus.DRAFT,
        adjustment_type="regular",
        created_by=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_legacy_run_cannot_enter_new_review_workflow(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    run = _legacy_run(db)
    response = client.post(f"{API}/runs/{run.id}/start-review", headers=superuser_token_headers)
    assert response.status_code == 409
    db.refresh(run)
    assert run.workflow_status == "draft"


def test_legacy_run_cannot_be_finalized(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    run = _legacy_run(db)
    response = client.post(f"{API}/runs/{run.id}/finalize", headers=superuser_token_headers)
    assert response.status_code == 503
    assert "disabled until HR approves" in response.json()["detail"]
    db.refresh(run)
    assert run.status == PayrollRunStatus.DRAFT
    assert run.frozen_snapshot is None


def test_authorized_payroll_user_can_read_draft_for_review(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    run = _legacy_run(db)
    response = client.get(f"{API}/runs/{run.id}", headers=superuser_token_headers)
    assert response.status_code == 200, response.text
    assert response.json()["workflow_status"] == "draft"
