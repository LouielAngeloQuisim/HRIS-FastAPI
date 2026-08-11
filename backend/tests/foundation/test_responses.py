"""Phase 0 Item 6 - base response envelope, pagination, error format, audit."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.common.audit.redactor import redact_payload
from app.common.audit.sink import (
    AuditRecord,
    AuditSink,
    LogSink,
    get_audit_sink,
    set_audit_sink,
)
from app.common.pagination import make_meta, total_pages
from app.common.responses import (
    ErrorResponse,
    Meta,
    ResponseModel,
)
from app.main import app


class CapturingSink(AuditSink):
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def emit(self, record: AuditRecord) -> None:
        self.records.append(record)


@pytest.fixture
def audit_sink():
    sink = CapturingSink()
    set_audit_sink(sink)
    yield sink
    set_audit_sink(LogSink())


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# --- response envelope + pagination ---------------------------------------


def test_meta_page_detection():
    meta = make_meta(total=100, skip=0, limit=20, count=20)
    assert meta.has_more is True
    assert meta.count == 20
    last = make_meta(total=100, skip=80, limit=20, count=20)
    assert last.has_more is False


def test_total_pages():
    assert total_pages(0, 20) == 0
    assert total_pages(1, 20) == 1
    assert total_pages(100, 20) == 5


def test_response_envelope_serializes():
    env = ResponseModel[str](data="ok", request_id="r1")
    dumped = env.model_dump()
    assert dumped["success"] is True
    assert dumped["data"] == "ok"
    assert dumped["request_id"] == "r1"


# --- error format ----------------------------------------------------------


def test_validation_error_is_structured(client: TestClient):
    # Signup with an empty body -> pydantic validation error. The handler must
    # produce the structured error envelope (not a raw FastAPI dict).
    # Q12: signup is admin-gated, so authenticate with the superuser token first.
    from tests.utils.utils import get_superuser_token_headers

    headers = get_superuser_token_headers(client)
    r = client.post("/api/v1/users/signup", json={}, headers=headers)
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False
    assert body["error"]["type"] == "validation_error"
    assert body["detail"]  # preserved for compatibility
    assert body["error"]["details"]  # field-level problems
    assert "request_id" in body


def test_login_failure_returns_structured_error(client: TestClient):
    r = client.post(
        "/api/v1/login/access-token",
        data={"username": f"{uuid.uuid4()}@example.com", "password": "nope"},
    )
    assert r.status_code in (400, 401)
    body = r.json()
    assert body["success"] is False
    assert body["error"]["type"] == "http_error"
    assert body["request_id"]


# --- audit middleware ------------------------------------------------------


def test_request_id_header_is_set(client: TestClient):
    r = client.get("/api/v1/utils/health-check/")
    assert "x-request-id" in r.headers


def test_audit_redacts_password(client: TestClient, audit_sink: CapturingSink):
    email = f"{uuid.uuid4()}@example.com"
    client.post(
        "/api/v1/users/signup",
        json={"email": email, "password": "super-secret-value", "full_name": "X"},
    )
    assert audit_sink.records, "middleware emitted no audit record"
    record = audit_sink.records[0]
    assert record.request_id
    assert record.method == "POST"
    assert record.path.endswith("/users/signup")
    # The body was captured (JSON) and the password redacted.
    assert record.redacted_body is not None
    assert "super-secret-value" not in record.redacted_body
    assert "[REDACTED]" in record.redacted_body


def test_audit_captures_authenticated_actor(
    client: TestClient, audit_sink: CapturingSink, db
):
    from app.user.services import create_user
    from app.user.models import UserCreate
    from tests.utils.utils import random_email, random_lower_string

    plain = random_lower_string()
    user = create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=plain),
    )
    token = client.post(
        "/api/v1/login/access-token",
        data={"username": user.email, "password": plain},
    ).json()["access_token"]
    # A call we know requires auth and succeeds.
    client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    actor_record = next(
        (r for r in audit_sink.records if r.user_id == str(user.id)), None
    )
    assert actor_record is not None, "authenticated user id not recorded"
    assert actor_record.user_email == user.email


# --- redactor unit ---------------------------------------------------------


def test_redact_payload_nested():
    payload = {
        "username": "bob",
        "password": "hunter2",
        "inner": {"token": "abc", "keep": "yes"},
        "items": [{"secret": "x"}],
    }
    out = redact_payload(payload)
    assert out["password"] == "[REDACTED]"
    assert out["inner"]["token"] == "[REDACTED]"
    assert out["inner"]["keep"] == "yes"
    assert out["items"][0]["secret"] == "[REDACTED]"
    # original untouched
    assert payload["password"] == "hunter2"
