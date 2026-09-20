"""Phase B5 — audit route tests."""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.audit.models import AuditLog
from app.config.settings import settings
from app.user.models import User

API = settings.API_V1_STR


def _get_superuser_id(db: Session) -> uuid.UUID:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user is not None
    return user.id


def test_list_audit_logs(client: TestClient, superuser_token_headers: dict[str, str], db: Session) -> None:
    user_id = _get_superuser_id(db)
    log = AuditLog(
        method="GET",
        path="/api/v1/test",
        status_code=200,
        duration_ms=12.5,
        user_id=user_id,
        user_email="test@example.com",
        ip_address="127.0.0.1",
        user_agent="test",
        module="test",
        action="view",
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    r = client.get(f"{API}/audit-log/", headers=superuser_token_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "data" in data
    assert "count" in data
    assert data["count"] >= 1


def test_get_audit_log_detail(client: TestClient, superuser_token_headers: dict[str, str], db: Session) -> None:
    user_id = _get_superuser_id(db)
    log = AuditLog(
        method="POST",
        path="/api/v1/test",
        status_code=201,
        duration_ms=5.0,
        user_id=user_id,
        user_email="test@example.com",
        ip_address="127.0.0.1",
        user_agent="test",
        module="test",
        action="add",
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    r = client.get(f"{API}/audit-log/{log.id}", headers=superuser_token_headers)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == str(log.id)


def test_get_audit_log_not_found(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    fake_id = str(uuid.uuid4())
    r = client.get(f"{API}/audit-log/{fake_id}", headers=superuser_token_headers)
    assert r.status_code == 404, r.text
