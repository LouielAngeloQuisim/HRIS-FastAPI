"""Phase B5 — audit redaction: no plaintext secrets/salary persisted."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.audit.models import AuditLog
from app.audit.sink import DBAuditSink
from app.common.audit.redactor import redact_json, redact_payload
from app.common.audit.sink import AuditRecord
from app.config.database import engine
from app.config.settings import settings


class TestRedactor:
    def test_password_token_and_salary_are_redacted(self) -> None:
        payload = {
            "email": "user@example.com",
            "password": "PlainSecret123!",
            "access_token": "eyJhbGciOi...",
            "basic_rate": 25000.0,
            "net_pay": 20000.0,
            "nested": {"refresh_token": "rt-secret", "gross_pay": 25000},
        }
        redacted = redact_payload(payload)
        assert redacted["password"] == "[REDACTED]"
        assert redacted["access_token"] == "[REDACTED]"
        assert redacted["basic_rate"] == "[REDACTED]"
        assert redacted["net_pay"] == "[REDACTED]"
        assert redacted["nested"]["refresh_token"] == "[REDACTED]"
        assert redacted["nested"]["gross_pay"] == "[REDACTED]"
        text = json.dumps(redacted)
        assert "PlainSecret123!" not in text
        assert "rt-secret" not in text

    def test_redact_json_handles_raw_body(self) -> None:
        body = json.dumps({"password": "hunter2", "salary": 99999})
        out = redact_json(body)
        assert out is not None
        assert "hunter2" not in out
        assert "99999" not in out
        assert "[REDACTED]" in out

    def test_redact_json_invalid_returns_none(self) -> None:
        assert redact_json("not-json") is None
        assert redact_json("") is None


class TestDBAuditSinkPersistence:
    def test_redacted_record_is_persisted(self) -> None:
        request_id = f"redact-{uuid.uuid4().hex[:8]}"
        raw = json.dumps(
            {
                "password": "PlainSecret123!",
                "access_token": "token-abc",
                "basic_rate": 12345.67,
            }
        )
        body = redact_json(raw)
        assert body is not None

        DBAuditSink().emit(
            AuditRecord(
                request_id=request_id,
                method="POST",
                path="/api/v1/payroll/runs/preview",
                status_code=200,
                duration_ms=1.0,
                redacted_body=body,
            )
        )

        with Session(engine) as session:
            log = session.exec(select(AuditLog).where(AuditLog.request_id == request_id)).first()
        assert log is not None
        assert log.redacted_body is not None
        assert "PlainSecret123!" not in log.redacted_body
        assert "token-abc" not in log.redacted_body
        assert "12345.67" not in log.redacted_body
        assert "[REDACTED]" in log.redacted_body


class TestMiddlewareRedaction:
    def test_json_body_secrets_never_reach_audit_log(self, client: TestClient) -> None:
        secret = f"PlainSecret-{uuid.uuid4().hex}"
        token = f"token-{uuid.uuid4().hex}"
        resp = client.post(
            f"{settings.API_V1_STR}/users/",
            json={"email": "redact-test@example.com", "password": secret, "access_token": token},
        )
        # Whatever the auth outcome, the request must have been audited.
        assert resp.status_code in (200, 201, 401, 403, 422)

        with Session(engine) as session:
            rows = session.exec(
                select(AuditLog)
                .where(AuditLog.path == f"{settings.API_V1_STR}/users/")
                .order_by(AuditLog.created_at.desc())  # type: ignore[arg-type]
            ).all()
        assert rows, "no audit log row was persisted for the request"
        combined = " ".join(r.redacted_body or "" for r in rows)
        assert secret not in combined
        assert token not in combined
        assert "[REDACTED]" in combined
