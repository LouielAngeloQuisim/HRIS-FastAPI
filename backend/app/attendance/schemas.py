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
