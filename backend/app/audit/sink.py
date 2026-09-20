"""Phase B5 — DB-backed audit sink + query helpers."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Session, select

from app.audit.models import AuditLog
from app.common.audit.sink import AuditRecord, AuditSink


class DBAuditSink(AuditSink):
    """Persist AuditRecords to Postgres."""

    def emit(self, record: AuditRecord) -> None:
        try:
            from sqlmodel import Session as _Session

            from app.config.database import engine
            with _Session(engine) as session:
                log = AuditLog(
                    request_id=record.request_id,
                    method=record.method,
                    path=record.path,
                    status_code=record.status_code,
                    duration_ms=record.duration_ms,
                    user_id=record.user_id,
                    user_email=record.user_email,
                    ip_address=record.ip_address,
                    user_agent=record.user_agent,
                    module=record.module,
                    action=record.action,
                    redacted_body=record.redacted_body,
                    error=record.error,
                    security_event=record.security_event.value if record.security_event else None,
                    extra=record.extra if record.extra else None,
                )
                session.add(log)
                session.commit()
        except Exception:  # pragma: no cover - never break the request
            pass


def list_audit_logs(
    session: Session,
    *,
    user_id: str | None = None,
    module: str | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog).where(AuditLog.is_deleted == False)  # noqa: E712
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if module is not None:
        stmt = stmt.where(AuditLog.module == module)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if date_from is not None:
        stmt = stmt.where(AuditLog.created_at >= date_from)  # type: ignore[operator]
    if date_to is not None:
        stmt = stmt.where(AuditLog.created_at <= date_to)  # type: ignore[operator]
    count = len(session.exec(stmt).all())
    rows = session.exec(
        stmt.offset(skip).limit(limit).order_by(AuditLog.created_at.desc())  # type: ignore[union-attr]
    ).all()
    return list(rows), count


def get_audit_log(session: Session, log_id: uuid.UUID) -> AuditLog | None:
    return session.get(AuditLog, log_id)
