"""Request/response DTOs for the attendance resources (design §1, §7)."""

import uuid
from datetime import date, datetime

from pydantic import model_validator
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


class EmployeeShiftAssignmentCreate(SQLModel):
    employee_id: uuid.UUID | None = None
    employee_code: str | None = Field(default=None, min_length=1, max_length=64)
    shift_id: uuid.UUID
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def require_employee_identity(self) -> "EmployeeShiftAssignmentCreate":
        if (self.employee_id is None) == (self.employee_code is None):
            raise ValueError("Provide exactly one of employee_id or employee_code")
        return self


class EmployeeShiftAssignmentUpdate(SQLModel):
    effective_to: date | None = None


class EmployeeShiftAssignmentPublic(SQLModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    shift_id: uuid.UUID
    effective_from: date
    effective_to: date | None
    assigned_by: uuid.UUID | None
    created_at: datetime | None
    updated_at: datetime | None


class EmployeeShiftAssignmentList(SQLModel):
    data: list[EmployeeShiftAssignmentPublic]
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


class OvertimeDecision(SQLModel):
    approved_minutes: int | None = Field(default=None, ge=0)
    reason: str = Field(min_length=1, max_length=1024)


class OvertimeDecisionPublic(SQLModel):
    id: uuid.UUID
    daily_time_record_id: uuid.UUID
    status: str
    eligible_minutes: int
    approved_minutes: int
    reason: str
    decided_by: uuid.UUID | None
    created_at: datetime | None


class DtrIntervalInput(SQLModel):
    start_at: datetime
    end_at: datetime
    original_row: dict[str, object] = Field(default_factory=dict)


class DtrIntervalsUpdate(SQLModel):
    intervals: list[DtrIntervalInput] = Field(min_length=1, max_length=20)


class DtrAttendanceIntervalPublic(SQLModel):
    id: uuid.UUID
    daily_time_record_id: uuid.UUID
    revision: int
    sequence: int
    start_at: datetime
    end_at: datetime
    original_row: dict[str, object]
    created_by: uuid.UUID | None
    created_at: datetime | None


class DailyTimeRecordPublic(SQLModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    shift_id: uuid.UUID | None
    login_date: datetime | None
    logout_date: datetime | None
    work_date: date | None
    rendered_minutes: int | None
    late_minutes: int | None
    undertime_minutes: int | None
    overtime_minutes: int | None
    overtime_approved: bool | None
    overtime_approved_minutes: int | None = None
    overtime_decision_reason: str | None = None
    overtime_decided_by: uuid.UUID | None = None
    overtime_decided_at: datetime | None = None
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
    keys: list[ReconcilePair] = Field(
        default_factory=list, max_length=RECONCILE_MAX_KEYS
    )


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


class DtrImportInterval(SQLModel):
    start_at: datetime
    end_at: datetime
    original_row: dict[str, str] = Field(default_factory=dict)


class DtrImportRow(SQLModel):
    employee_code: str = Field(min_length=1, max_length=64)
    login_date: datetime
    logout_date: datetime
    shift_code: str | None = Field(default=None, max_length=32)
    source_row: dict[str, str] = Field(default_factory=dict)
    intervals: list[DtrImportInterval] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_interval_order(self) -> "DtrImportRow":
        if not self.intervals:
            return self
        if len(self.intervals) < 2:
            raise ValueError("Provide multiple intervals only when explicitly merging duplicate daily rows")
        ordered = sorted(self.intervals, key=lambda interval: interval.start_at)
        if ordered[0].start_at != self.login_date or ordered[-1].end_at != self.logout_date:
            raise ValueError("login_date and logout_date must match the first and last merged interval")
        for interval in ordered:
            if interval.end_at <= interval.start_at:
                raise ValueError("Every attendance interval must end after it starts")
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.start_at < previous.end_at:
                raise ValueError("Merged attendance intervals cannot overlap")
        return self


class DtrImportBatchRequest(SQLModel):
    batch_id: uuid.UUID
    rows: list[DtrImportRow] = Field(min_length=1, max_length=1000)


class DtrImportIssue(SQLModel):
    row_index: int
    employee_code: str
    work_date: date | None = None
    code: str
    message: str


class DtrImportExcluded(SQLModel):
    row_index: int
    employee_code: str
    existing_record_id: uuid.UUID
    reason: str


class DtrImportPreflightResponse(SQLModel):
    batch_id: uuid.UUID
    payload_fingerprint: str
    valid: bool
    row_count: int
    issues: list[DtrImportIssue]
    excluded: list[DtrImportExcluded]


class DtrImportBatchCommitResponse(SQLModel):
    batch_id: uuid.UUID
    created_count: int
    replayed: bool
    excluded_count: int
    records: list[DailyTimeRecordPublic]


class DtrImportBatchPublic(SQLModel):
    id: uuid.UUID
    created_by: uuid.UUID | None
    row_count: int
    created_count: int
    excluded_count: int
    source_rows: list[dict[str, object]]
    submitted_rows: list[dict[str, object]]
    corrections: list[dict[str, object]]
    created_at: datetime | None
