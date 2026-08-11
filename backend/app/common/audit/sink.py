"""Audit sinks.

A sink receives an `AuditRecord` after each request. The default `LogSink`
emits a structured log line. A DB-backed sink is wired in Phase 5; it is gated
behind `AUDIT_DB_SINK`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("hris.audit")


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
    extra: dict[str, Any] = field(default_factory=dict)

    def to_log_dict(self) -> dict[str, Any]:
        return {
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
            **self.extra,
        }


class AuditSink:
    """Base sink. Override `emit`."""

    def emit(self, record: AuditRecord) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class LogSink(AuditSink):
    def emit(self, record: AuditRecord) -> None:
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


# Re-export so the middleware can decide at runtime without import cycles.
AUDIT_DB_SINK = "db"
