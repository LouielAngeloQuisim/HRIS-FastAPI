"""Phase B5 — Audit log model.

Stores append-only audit records emitted by the middleware/security logger.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Text
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    request_id: str | None = Field(default=None, max_length=64, index=True)
    method: str = Field(max_length=10)
    path: str = Field(max_length=512)
    status_code: int | None = Field(default=None)
    duration_ms: float | None = Field(default=None)
    user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True, ondelete="SET NULL")
    user_email: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=64)
    user_agent: str | None = Field(default=None, max_length=512)
    module: str | None = Field(default=None, max_length=128)
    action: str | None = Field(default=None, max_length=128)
    redacted_body: str | None = Field(default=None, sa_type=Text)
    error: str | None = Field(default=None, sa_type=Text)
    security_event: str | None = Field(default=None, max_length=64)
    extra: dict[str, Any] | None = Field(default=None, sa_type=JSON)
    is_deleted: bool = Field(default=False)
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore

    __table_args__ = (
        Index("ix_audit_log_user_created", "user_id", "created_at"),
        Index("ix_audit_log_created", "created_at"),
    )
