"""Audit trail: redaction, sinks, and request middleware.

Phase 0 ships the middleware + a redacting logging sink. A persistent DB sink
lands in Phase 5; it is gated behind `AUDIT_DB_SINK` so no migration is
required to boot in Phase 0.
"""

from __future__ import annotations

from .middleware import AuditMiddleware
from .redactor import redact_payload
from .sink import AuditRecord, LogSink, get_audit_sink

__all__ = [
    "AuditMiddleware",
    "AuditRecord",
    "LogSink",
    "get_audit_sink",
    "redact_payload",
]
