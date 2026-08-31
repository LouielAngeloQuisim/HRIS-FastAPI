"""Phase 2B entities: DTR adjustment approval flow.

A DtrAdjustment is a proposed correction to an existing time record's
login/logout times. It carries a status state machine (PENDING -> APPROVED |
REJECTED) and, only on approval, applies the adjusted times to the underlying
DailyTimeRecord and recomputes it via the calc core.

Legacy ``DTRAdjutments`` had no auth and no approval (analysis §7); both are
added here. Permissions reuse the existing ``daily_time_record`` module.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class DtrAdjustment(SQLModel, table=True):
    """Proposed correction to a time record, pending approval."""

    __tablename__ = "dtr_adjustment"
    __table_args__ = (
        Index("ix_dtr_adjustment_dtr_deleted", "daily_time_record_id", "is_deleted"),
        Index("ix_dtr_adjustment_status_deleted", "status", "is_deleted"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    daily_time_record_id: uuid.UUID = Field(
        default=None, foreign_key="daily_time_record.id", index=True, ondelete="CASCADE"
    )
    employee_id: uuid.UUID = Field(
        default=None, foreign_key="employee_records.id", index=True, ondelete="CASCADE"
    )
    original_login_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    original_logout_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    adjusted_login_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    adjusted_logout_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    reason: str | None = Field(default=None, max_length=1024)
    status: str = Field(default="PENDING", max_length=16, index=True)
    adjusted_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", index=True, ondelete="SET NULL"
    )
    approved_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", index=True, ondelete="SET NULL"
    )
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)  # type: ignore
    )
