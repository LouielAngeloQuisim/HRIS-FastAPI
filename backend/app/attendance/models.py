"""Phase 2A entities: Attendance/DTR time math core (design §1).

Conventions (uniform with Phase 0-1):
- UUID PKs, snake_case singular table names via ``__tablename__``.
- Uniform soft delete: ``is_deleted`` (NOT NULL DEFAULT false) + ``deleted_at``.
- Composite indexes pair ``is_deleted`` with the FK it is filtered alongside.
- ``get_datetime_utc`` redefined per-module to match the Phase 0 pattern.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Index, UniqueConstraint, text
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
    days_of_week: list[str] = Field(
        default_factory=lambda: ["1", "2", "3", "4", "5"], sa_type=JSON
    )
    description: str | None = Field(default=None, max_length=1024)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class EmployeeShiftAssignment(SQLModel, table=True):
    """Effective-dated shift history for an employee; date bounds are inclusive."""

    __tablename__ = "employee_shift_assignment"
    __table_args__ = (
        Index(
            "ix_employee_shift_assignment_employee_dates",
            "employee_id",
            "effective_from",
            "effective_to",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID = Field(
        foreign_key="employee_records.id", index=True, ondelete="CASCADE"
    )
    shift_id: uuid.UUID = Field(foreign_key="shift.id", index=True, ondelete="RESTRICT")
    effective_from: date
    effective_to: date | None = None
    assigned_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    is_deleted: bool = Field(default=False)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )  # type: ignore
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )  # type: ignore


class DtrImportBatch(SQLModel, table=True):
    """Durable idempotency identity for an atomically committed CSV batch."""

    __tablename__ = "dtr_import_batch"
    __table_args__ = (Index("ix_dtr_import_batch_created_at", "created_at"),)

    id: uuid.UUID = Field(primary_key=True)
    payload_fingerprint: str = Field(max_length=64)
    created_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    row_count: int
    created_count: int = Field(default=0)
    excluded_count: int = Field(default=0)
    source_rows: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    submitted_rows: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    corrections: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )  # type: ignore


class DailyTimeRecord(SQLModel, table=True):
    """One paired IN/OUT punch, or one absence row. Legacy ``worker_logs``."""

    __tablename__ = "daily_time_record"
    __table_args__ = (
        Index("ix_daily_time_record_employee_deleted", "employee_id", "is_deleted"),
        Index("ix_daily_time_record_shift_deleted", "shift_id", "is_deleted"),
        Index("ix_daily_time_record_employee_login", "employee_id", "login_date"),
        Index("ix_daily_time_record_employee_work_date", "employee_id", "work_date"),
        Index(
            "uq_daily_time_record_employee_work_date_active",
            "employee_id",
            "work_date",
            unique=True,
            postgresql_where=text("is_deleted = false AND work_date IS NOT NULL"),
            sqlite_where=text("is_deleted = 0 AND work_date IS NOT NULL"),
        ),
        CheckConstraint(
            "overtime_approved_minutes IS NULL OR overtime_approved_minutes >= 0",
            name="ck_daily_time_record_overtime_approved_minutes_nonnegative",
        ),
        CheckConstraint(
            "overtime_approved_minutes IS NULL OR (overtime_minutes IS NOT NULL AND overtime_approved_minutes <= overtime_minutes)",
            name="ck_daily_time_record_overtime_approved_minutes_bounded",
        ),
        # QA-01 import idempotency: at most one ACTIVE row per (employee,
        # opaque import key), enforced by the database so concurrent retries
        # serialize. Soft-deleted rows are excluded so a fresh deliberate
        # import under the same key can still create a new row.
        Index(
            "uq_daily_time_record_source_ref_active",
            "employee_id",
            "source_ref",
            unique=True,
            postgresql_where=text("is_deleted = false AND source_ref IS NOT NULL"),
            sqlite_where=text("is_deleted = 0 AND source_ref IS NOT NULL"),
        ),
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
    work_date: date | None = Field(default=None, index=True)
    rendered_minutes: int | None = Field(default=None)
    late_minutes: int | None = Field(default=None)
    undertime_minutes: int | None = Field(default=None)
    overtime_minutes: int | None = Field(default=None)
    overtime_approved: bool | None = Field(default=None)
    overtime_approved_minutes: int | None = Field(default=None)
    overtime_decision_reason: str | None = Field(default=None, max_length=1024)
    overtime_decided_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    overtime_decided_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )  # type: ignore
    interval_revision: int = Field(default=0)
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
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class DtrOvertimeDecision(SQLModel, table=True):
    """Append-only audit record for an overtime approval or rejection."""

    __tablename__ = "dtr_overtime_decision"
    __table_args__ = (
        Index("ix_dtr_overtime_decision_record_created", "daily_time_record_id", "created_at"),
        CheckConstraint(
            "status IN ('approved', 'rejected')",
            name="ck_dtr_overtime_decision_status",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    daily_time_record_id: uuid.UUID = Field(
        foreign_key="daily_time_record.id", index=True, ondelete="CASCADE"
    )
    status: str = Field(max_length=16)
    eligible_minutes: int
    approved_minutes: int
    reason: str = Field(max_length=1024)
    decided_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )  # type: ignore


class DtrAttendanceInterval(SQLModel, table=True):
    """Immutable interval history; only the highest current revision is active."""

    __tablename__ = "dtr_attendance_interval"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_dtr_interval_positive_duration"),
        UniqueConstraint(
            "daily_time_record_id", "revision", "sequence",
            name="uq_dtr_interval_revision_sequence",
        ),
        Index(
            "ix_dtr_interval_record_current_revision",
            "daily_time_record_id",
            "revision",
            "sequence",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    daily_time_record_id: uuid.UUID = Field(
        foreign_key="daily_time_record.id", index=True, ondelete="CASCADE"
    )
    revision: int
    sequence: int
    start_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    end_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    original_row: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    created_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )  # type: ignore
