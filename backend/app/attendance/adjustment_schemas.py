"""Request/response DTOs for DTR adjustments (design §2B)."""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class DtrAdjustmentCreate(SQLModel):
    daily_time_record_id: uuid.UUID
    adjusted_login_date: datetime
    adjusted_logout_date: datetime
    reason: str | None = Field(default=None, max_length=1024)
    adjusted_date: datetime | None = None


class DtrAdjustmentUpdate(SQLModel):
    adjusted_login_date: datetime | None = None
    adjusted_logout_date: datetime | None = None
    reason: str | None = Field(default=None, max_length=1024)
    adjusted_date: datetime | None = None


class DtrAdjustmentPublic(SQLModel):
    id: uuid.UUID
    daily_time_record_id: uuid.UUID
    employee_id: uuid.UUID
    original_login_date: datetime | None
    original_logout_date: datetime | None
    adjusted_login_date: datetime | None
    adjusted_logout_date: datetime | None
    reason: str | None
    status: str
    adjusted_date: datetime | None
    created_by: uuid.UUID | None
    approved_by: uuid.UUID | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class DtrAdjustmentList(SQLModel):
    data: list[DtrAdjustmentPublic]
    count: int
