"""Security audit logging tests.

Verifies the `log_security_event` integration added to:
- `app/user/routes/auth.py` (login success/fail, logout, refresh, password reset)
- `app/rbac/dependencies.py` (PERMISSION_DENIED)

The existing `test_responses.py` covers the middleware path. This file
focuses on the explicit security-event helper and the auth-route call sites.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.common.audit.sink import (
    AuditRecord,
    AuditSink,
    LogSink,
    SecurityEventType,
    log_security_event,
    set_audit_sink,
)
from app.config.settings import settings
from app.user.models import User, UserCreate
from app.user.services import create_user
from tests.utils.utils import random_email, random_lower_string


class CapturingSink(AuditSink):
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def emit(self, record: AuditRecord) -> None:
        self.records.append(record)

    def security_records(self) -> list[AuditRecord]:
        return [r for r in self.records if r.security_event is not None]


@pytest.fixture
def security_sink() -> CapturingSink:
    sink = CapturingSink()
    set_audit_sink(sink)
    yield sink
    set_audit_sink(LogSink())


# --- direct log_security_event() unit tests -------------------------------


def test_log_security_event_emits_record(security_sink: CapturingSink) -> None:
    log_security_event(
        security_event=SecurityEventType.LOGIN_SUCCESS,
        user_id="user-1",
        user_email="a@example.com",
        ip_address="127.0.0.1",
        user_agent="ua",
    )
    sec = security_sink.security_records()
    assert len(sec) == 1
    assert sec[0].security_event == SecurityEventType.LOGIN_SUCCESS
    assert sec[0].user_id == "user-1"
    assert sec[0].user_email == "a@example.com"
    assert sec[0].ip_address == "127.0.0.1"
    assert sec[0].user_agent == "ua"
    assert sec[0].method == "SECURITY"
    assert sec[0].status_code == 0


def test_log_security_event_preserves_extra(security_sink: CapturingSink) -> None:
    log_security_event(
        security_event=SecurityEventType.PERMISSION_DENIED,
        module="division",
        action="delete",
    )
    rec = security_sink.security_records()[0]
    # module/action come in as **extra kwargs and land in the extra dict, not
    # the top-level dataclass fields (those are reserved for the request path).
    assert rec.extra.get("module") == "division"
    assert rec.extra.get("action") == "delete"
    # But they DO surface in the serialised log output.
    dumped = rec.to_log_dict()
    assert dumped["module"] == "division"
    assert dumped["action"] == "delete"


def test_log_security_event_swallows_sink_errors() -> None:
    """A broken sink must never raise into the request path."""

    class BrokenSink(AuditSink):
        def emit(self, record: AuditRecord) -> None:
            raise RuntimeError("boom")

    set_audit_sink(BrokenSink())
    try:
        log_security_event(security_event=SecurityEventType.LOGIN_FAILED)
    finally:
        set_audit_sink(LogSink())


# --- auth route integration ----------------------------------------------


def test_login_success_emits_event(
    client: TestClient, security_sink: CapturingSink
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={
            "username": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    assert r.status_code == 200
    successes = [
        rec
        for rec in security_sink.security_records()
        if rec.security_event == SecurityEventType.LOGIN_SUCCESS
    ]
    assert len(successes) == 1
    assert successes[0].user_email == settings.FIRST_SUPERUSER


def test_login_failure_incorrect_credentials_emits_event(
    client: TestClient, security_sink: CapturingSink
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": f"{uuid.uuid4()}@example.com", "password": "wrong"},
    )
    assert r.status_code in (400, 401)
    failures = [
        rec
        for rec in security_sink.security_records()
        if rec.security_event == SecurityEventType.LOGIN_FAILED
    ]
    assert len(failures) == 1
    assert failures[0].extra.get("reason") == "incorrect_credentials"


def test_login_failure_inactive_user_emits_event(
    client: TestClient, security_sink: CapturingSink, db
) -> None:
    email = random_email()
    password = random_lower_string()
    user = create_user(
        session=db,
        user_create=UserCreate(email=email, password=password, is_active=False),
    )
    assert isinstance(user, User)

    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": email, "password": password},
    )
    assert r.status_code in (400, 401)
    failures = [
        rec
        for rec in security_sink.security_records()
        if rec.security_event == SecurityEventType.LOGIN_FAILED
        and rec.user_id == str(user.id)
    ]
    assert len(failures) == 1
    assert failures[0].extra.get("reason") == "inactive_account"


def test_logout_with_invalid_refresh_token_emits_event(
    client: TestClient, security_sink: CapturingSink
) -> None:
    """Logout is authenticated by the refresh token in the body, not a Bearer.

    A request to revoke a non-existent refresh token is rejected with 401 and
    the event is logged, but the actor is not attributed (no user record to
    attribute to, only a token hash).
    """
    r = client.post(
        f"{settings.API_V1_STR}/logout",
        json={"refresh_token": "not-a-real-token", "all_sessions": False},
    )
    assert r.status_code == 401
    logouts = [
        rec
        for rec in security_sink.security_records()
        if rec.security_event == SecurityEventType.LOGOUT
    ]
    assert len(logouts) == 1
    assert logouts[0].error is not None
    assert logouts[0].user_id is None  # no actor attribution from the body alone


def test_password_reset_request_unknown_email_does_not_emit(
    client: TestClient, security_sink: CapturingSink, normal_user_token_headers
) -> None:
    """User-enumeration prevention: an unknown email must NOT emit an audit event.

    The route returns 200 either way, so an attacker probing addresses cannot
    tell which exist. A real user email would emit, but that path is exercised
    by the integration tests for password recovery itself, not here.
    """
    email = f"{uuid.uuid4()}@example.com"
    r = client.post(
        f"{settings.API_V1_STR}/password-recovery/{email}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    events = [
        rec
        for rec in security_sink.security_records()
        if rec.security_event == SecurityEventType.PASSWORD_RESET_REQUEST
    ]
    assert events == []


# --- rbac PermissionChecker integration -----------------------------------


def test_permission_denied_emits_event(
    client: TestClient, security_sink: CapturingSink, normal_user_token_headers
) -> None:
    """A low-privilege user hitting a require_permission-gated route emits PERMISSION_DENIED."""
    r = client.get(
        f"{settings.API_V1_STR}/divisions/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403
    denials = [
        rec
        for rec in security_sink.security_records()
        if rec.security_event == SecurityEventType.PERMISSION_DENIED
    ]
    assert len(denials) >= 1
    latest = denials[-1]
    # module/action pass through **extra and surface in the serialised log.
    dumped = latest.to_log_dict()
    assert dumped["module"] == "division"
    assert dumped["action"] == "view"
    assert latest.user_id is not None
    assert latest.user_email is not None
