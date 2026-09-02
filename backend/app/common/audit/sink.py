"""Audit sinks.

A sink receives an `AuditRecord` after each request. The default `LogSink`
emits a structured log line. A DB-backed sink is wired in Phase 5; it is gated
behind `AUDIT_DB_SINK`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("hris.audit")


class SecurityEventType(str, Enum):
    """Security-specific event types for audit logging."""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REUSE_DETECTED = "token_reuse_detected"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET_REQUEST = "password_reset_request"
    PASSWORD_RESET_COMPLETE = "password_reset_complete"
    PERMISSION_DENIED = "permission_denied"
    ROLE_CHANGE = "role_change"
    ACCOUNT_LOCKED = "account_locked"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


@dataclass
class AuditRecord:
    request_id: str
    method: str
    path: str
    status_code: int
    duration_ms: float
    user_id: str | None = None
    user_email: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    module: str | None = None
    action: str | None = None
    redacted_body: str | None = None
    error: str | None = None
    security_event: SecurityEventType | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_log_dict(self) -> dict[str, Any]:
        result = {
            "request_id": self.request_id,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "duration_ms": round(self.duration_ms, 2),
            "user_id": self.user_id,
            "user_email": self.user_email,
            "ip": self.ip_address,
            "module": self.module,
            "action": self.action,
            "body": self.redacted_body,
        }
        if self.security_event:
            result["security_event"] = self.security_event.value
        if self.error:
            result["error"] = self.error
        result.update(self.extra)
        return result


class AuditSink:
    """Base sink. Override `emit`."""

    def emit(self, record: AuditRecord) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class LogSink(AuditSink):
    def emit(self, record: AuditRecord) -> None:
        # Security events get WARNING level, others get INFO
        if record.security_event:
            logger.warning(
                "audit:security",
                extra={"audit": record.to_log_dict()},
            )
        else:
            logger.info("audit", extra={"audit": record.to_log_dict()})


_sink: AuditSink | None = None


def get_audit_sink() -> AuditSink:
    global _sink
    if _sink is None:
        _sink = LogSink()
    return _sink


def set_audit_sink(sink: AuditSink) -> None:
    global _sink
    _sink = sink


def log_security_event(
    security_event: SecurityEventType,
    user_id: str | None = None,
    user_email: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    error: str | None = None,
    **extra: Any,
) -> None:
    """Log a security-specific event outside of the normal request flow."""
    from app.common.security import get_request_id

    record = AuditRecord(
        request_id=request_id or get_request_id(),
        method="SECURITY",
        path="/security",
        status_code=0,
        duration_ms=0.0,
        user_id=user_id,
        user_email=user_email,
        ip_address=ip_address,
        user_agent=user_agent,
        security_event=security_event,
        error=error,
        extra=extra,
    )
    try:
        get_audit_sink().emit(record)
    except Exception:  # pragma: no cover - never break the app
        pass


# Re-export so the middleware can decide at runtime without import cycles.
AUDIT_DB_SINK = "db"
