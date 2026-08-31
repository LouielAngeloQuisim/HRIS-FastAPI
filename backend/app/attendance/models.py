"""Phase 2A entities: Attendance/DTR time math core (design §1).

Conventions (uniform with Phase 0-1):
- UUID PKs, snake_case singular table names via ``__tablename__``.
- Uniform soft delete: ``is_deleted`` (NOT NULL DEFAULT false) + ``deleted_at``.
- Composite indexes pair ``is_deleted`` with the FK it is filtered alongside.
- ``get_datetime_utc`` redefined per-module to match the Phase 0 pattern.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Index
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class Shift(SQLModel, table=True):
    """What 'on time' vs 'late' is measured against. Legacy ``Shifts``."""

    __tablename__ = "shift"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    name: str = Field(max_length=255)
    start_time: str = Field(max_length=5)
    end_time: str = Field(max_length=5)
    lunch_break_duration: int = Field(default=60)
    total_hours_minus_lunch: int = Field(default=480)
    days_of_week: list[str] = Field(default_factory=lambda: ["1", "2", "3", "4", "5"], sa_type=JSON)  # type: ignore
    description: str | None = Field(default=None, max_length=1024)
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


class DailyTimeRecord(SQLModel, table=True):
    """One paired IN/OUT punch, or one absence row. Legacy ``worker_logs``."""

    __tablename__ = "daily_time_record"
    __table_args__ = (
        Index("ix_daily_time_record_employee_deleted", "employee_id", "is_deleted"),
        Index("ix_daily_time_record_shift_deleted", "shift_id", "is_deleted"),
        Index("ix_daily_time_record_employee_login", "employee_id", "login_date"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID = Field(
        default=None, foreign_key="employee_records.id", index=True, ondelete="CASCADE"
    )
    shift_id: uuid.UUID | None = Field(
        default=None, foreign_key="shift.id", index=True, ondelete="SET NULL"
    )
    login_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    logout_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    rendered_minutes: int | None = Field(default=None)
    late_minutes: int | None = Field(default=None)
    undertime_minutes: int | None = Field(default=None)
    overtime_minutes: int | None = Field(default=None)
    overtime_approved: bool | None = Field(default=None)
    is_absent: bool = Field(default=False)
    is_time_calculated: bool = Field(default=False)
    source: str = Field(max_length=16, default="manual")
    source_ref: str | None = Field(default=None, max_length=128)
    created_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", index=True, ondelete="SET NULL"
    )
    updated_by: uuid.UUID | None = Field(
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
