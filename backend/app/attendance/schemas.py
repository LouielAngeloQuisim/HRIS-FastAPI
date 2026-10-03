"""Request/response DTOs for the attendance resources (design §1, §7)."""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


# --- Shift ---------------------------------------------------------------------------
class ShiftBase(SQLModel):
    code: str = Field(max_length=32)
    name: str = Field(max_length=255)
    start_time: str = Field(max_length=5)
    end_time: str = Field(max_length=5)
    lunch_break_duration: int = Field(default=60, ge=0)
    total_hours_minus_lunch: int = 480
    days_of_week: list[str] = ["1", "2", "3", "4", "5"]
    description: str | None = Field(default=None, max_length=1024)


class ShiftCreate(ShiftBase):
    pass


class ShiftUpdate(SQLModel):
    code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    start_time: str | None = Field(default=None, max_length=5)
    end_time: str | None = Field(default=None, max_length=5)
    lunch_break_duration: int | None = Field(default=None, ge=0)
    total_hours_minus_lunch: int | None = None
    days_of_week: list[str] | None = None
    description: str | None = Field(default=None, max_length=1024)


class ShiftPublic(ShiftBase):
    id: uuid.UUID
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class ShiftList(SQLModel):
    data: list[ShiftPublic]
    count: int


# --- DailyTimeRecord -----------------------------------------------------------------
class DailyTimeRecordBase(SQLModel):
    login_date: datetime
    logout_date: datetime
    shift_id: uuid.UUID | None = None
    shift_code: str | None = None


class DailyTimeRecordCreate(DailyTimeRecordBase):
    employee_id: uuid.UUID | None = None
    employee_code: str | None = None
    # Opaque per-import-row identity (batch id + row index), NOT a natural key.
    # Retried requests carrying the same (employee_id, source_ref) are settled
    # by the partial unique index uq_daily_time_record_source_ref_active: a
    # committed replay returns the existing row (HTTP 200) instead of inserting
    # a duplicate (QA-01). Manual/keyless creates are unaffected.
    source_ref: str | None = Field(default=None, min_length=1, max_length=128)


class DailyTimeRecordUpdate(SQLModel):
    login_date: datetime | None = None
    logout_date: datetime | None = None
    shift_id: uuid.UUID | None = None
    shift_code: str | None = None


class DailyTimeRecordPublic(SQLModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    shift_id: uuid.UUID | None
    login_date: datetime | None
    logout_date: datetime | None
    rendered_minutes: int | None
    late_minutes: int | None
    undertime_minutes: int | None
    overtime_minutes: int | None
    overtime_approved: bool | None
    is_absent: bool
    is_time_calculated: bool
    source: str
    source_ref: str | None
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class DailyTimeRecordList(SQLModel):
    data: list[DailyTimeRecordPublic]
    count: int


# --- QA-01 import reconciliation -----------------------------------------------------

RECONCILE_MAX_KEYS = 200


class ReconcilePair(SQLModel):
    """One unresolved import identity to settle. employee_code (not UUID) keeps
    the wizard's CSV vocabulary; the server resolves and scopes it."""

    employee_code: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1, max_length=128)


class ReconcileRequest(SQLModel):
    keys: list[ReconcilePair] = Field(default_factory=list, max_length=RECONCILE_MAX_KEYS)


class ReconcileResult(SQLModel):
    employee_code: str
    source_ref: str
    # committed  : exactly one ACTIVE row for this (employee, key) — safe to mark success
    # deleted    : a row for this key exists but was soft-deleted — never auto-replay
    # not_found  : fully checked within the caller's visible scope and absent.
    #              NOT proof of non-commit for an in-flight original: retries must
    #              keep the same key so the race-safe create path dedupes a late commit.
    status: str
    record_id: uuid.UUID | None = None


class ReconcileResponse(SQLModel):
    results: list[ReconcileResult]
    # Keys the caller could not be given a definite verdict for (unknown employee,
    # or outside the caller's row-level visibility). The wizard MUST keep these
    # UNKNOWN — absence of permission is not absence of data.
    unresolved: int
    requested: int
