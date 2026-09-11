"""Request/response DTOs for the leave domain (design doc §1.2)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from app.leave.models import (
    GenderScope,
    HolidayType,
    LeaveCadence,
    LeaveLedgerSource,
    LeaveRequestEventType,
    LeaveStatus,
    MaritalStatusScope,
    ObserveWeekendAs,
)


class LeavePolicyBase(SQLModel):
    code: str = Field(max_length=32)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    calendar_color: str = Field(max_length=7, default="#3B82F6")
    cadence: LeaveCadence = Field(default=LeaveCadence.ANNUAL)
    annual_entitlement_days: Decimal = Field(default=Decimal("0.00"))
    prorate_on_hire: bool = Field(default=False)
    carry_over_enabled: bool = Field(default=False)
    carry_over_max_days: Decimal | None = Field(default=None)
    carry_over_expires_on: date | None = Field(default=None)
    is_paid: bool = Field(default=True)
    eligible_departments: list[uuid.UUID] = Field(default_factory=list)
    gender_scope: GenderScope = Field(default=GenderScope.ALL)
    marital_status_scope: MaritalStatusScope = Field(default=MaritalStatusScope.ALL)
    is_active: bool = Field(default=True)


class LeavePolicyCreate(LeavePolicyBase):
    pass


class LeavePolicyUpdate(SQLModel):
    code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    calendar_color: str | None = Field(default=None, max_length=7)
    cadence: LeaveCadence | None = Field(default=None)
    annual_entitlement_days: Decimal | None = Field(default=None)
    prorate_on_hire: bool | None = Field(default=None)
    carry_over_enabled: bool | None = Field(default=None)
    carry_over_max_days: Decimal | None = Field(default=None)
    carry_over_expires_on: date | None = Field(default=None)
    is_paid: bool | None = Field(default=None)
    eligible_departments: list[uuid.UUID] | None = Field(default=None)
    gender_scope: GenderScope | None = Field(default=None)
    marital_status_scope: MaritalStatusScope | None = Field(default=None)
    is_active: bool | None = Field(default=None)


class LeavePolicyPublic(LeavePolicyBase):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    is_system: bool
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class LeavePolicyList(SQLModel):
    data: list[LeavePolicyPublic]
    count: int


# === EmployeeLeaveEnrollment ============================================================


class EmployeeLeaveEnrollmentBase(SQLModel):
    policy_id: uuid.UUID
    leave_year: int = Field(default=2026)


class EmployeeLeaveEnrollmentCreate(EmployeeLeaveEnrollmentBase):
    pass


class EmployeeLeaveEnrollmentPublic(SQLModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    policy_id: uuid.UUID
    leave_year: int
    granted_days: Decimal
    is_active: bool
    is_transferred: bool
    transferred_at: datetime | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class EmployeeLeaveEnrollmentList(SQLModel):
    data: list[EmployeeLeaveEnrollmentPublic]
    count: int


# === LeaveRequest ========================================================================


class LeaveRequestBase(SQLModel):
    employee_id: uuid.UUID
    policy_id: uuid.UUID
    date_start: date
    date_end: date
    requested_hours: Decimal | None = Field(default=None)
    reason: str | None = Field(default=None, max_length=1024)
    document_ref: str | None = Field(default=None, max_length=255)


class LeaveRequestCreate(LeaveRequestBase):
    pass


class LeaveRequestPublic(SQLModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    employee_id: uuid.UUID
    policy_id: uuid.UUID
    enrollment_id: uuid.UUID | None
    date_start: date
    date_end: date
    requested_hours: Decimal | None
    total_days_requested: Decimal
    reason: str | None
    document_ref: str | None
    status: LeaveStatus
    created_by_user: uuid.UUID | None
    approved_by_user: uuid.UUID | None
    approved_at: datetime | None
    rejected_by_user: uuid.UUID | None
    rejected_at: datetime | None
    cancelled_by_user: uuid.UUID | None
    cancelled_at: datetime | None
    decision_note: str | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class LeaveRequestList(SQLModel):
    data: list[LeaveRequestPublic]
    count: int


# === LeaveRequestEvent ===================================================================


class LeaveRequestEventPublic(SQLModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    request_id: uuid.UUID
    event: LeaveRequestEventType
    actor_user_id: uuid.UUID | None
    at: datetime | None
    note: str | None
    run_id: str | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class LeaveRequestDetail(SQLModel):
    request: LeaveRequestPublic
    events: list[LeaveRequestEventPublic]


# === LeaveLedgerEntry ===================================================================


class LeaveLedgerEntryPublic(SQLModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    employee_id: uuid.UUID
    policy_id: uuid.UUID
    enrollment_id: uuid.UUID | None
    leave_year: int
    source: LeaveLedgerSource
    amount: Decimal
    reference: str | None
    original_year: int | None
    note: str | None
    actor_user_id: uuid.UUID | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class LeaveLedgerSummary(SQLModel):
    granted_total: Decimal
    consumed_total: Decimal
    remaining: Decimal


class LeaveLedgerResponse(SQLModel):
    data: list[LeaveLedgerEntryPublic]
    summary: LeaveLedgerSummary


class LeaveLedgerEventPage(SQLModel):
    data: list[LeaveLedgerEntryPublic]
    pagination: dict[str, Any]
    summary: LeaveLedgerSummary


# === HolidayConfig ======================================================================


class HolidayConfigBase(SQLModel):
    code: str = Field(max_length=32)
    name: str = Field(max_length=255)
    month_day: str = Field(max_length=5)
    type: HolidayType = Field(default=HolidayType.REGULAR)
    region_code: str | None = Field(default=None, max_length=32)
    observe_weekend_as: ObserveWeekendAs | None = Field(default=None)
    multiplier_regular: Decimal | None = Field(default=None)
    multiplier_overtime: Decimal | None = Field(default=None)
    is_recurring: bool = Field(default=True)
    is_active: bool = Field(default=True)


class HolidayConfigCreate(HolidayConfigBase):
    pass


class HolidayConfigUpdate(SQLModel):
    code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    month_day: str | None = Field(default=None, max_length=5)
    type: HolidayType | None = Field(default=None)
    region_code: str | None = Field(default=None, max_length=32)
    observe_weekend_as: ObserveWeekendAs | None = Field(default=None)
    multiplier_regular: Decimal | None = Field(default=None)
    multiplier_overtime: Decimal | None = Field(default=None)
    is_recurring: bool | None = Field(default=None)
    is_active: bool | None = Field(default=None)


class HolidayConfigPublic(HolidayConfigBase):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class HolidayConfigList(SQLModel):
    data: list[HolidayConfigPublic]
    count: int


# === HolidayInstance =====================================================================


class HolidayInstanceBase(SQLModel):
    config_id: uuid.UUID
    observed_date: date
    raw_date: date | None = Field(default=None)
    leave_year: int


class HolidayInstanceCreate(HolidayInstanceBase):
    pass


class HolidayInstancePublic(SQLModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    config_id: uuid.UUID
    observed_date: date
    raw_date: date | None
    leave_year: int
    is_active: bool
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class HolidayInstanceList(SQLModel):
    data: list[HolidayInstancePublic]
    count: int


# === Calendar ===========================================================================


class LeaveCalendarEvent(SQLModel):
    id: uuid.UUID
    observed_date: date
    title: str
    status: LeaveStatus | None
    color: str
    type: str  # 'request' | 'holiday'


# === Admin actions ======================================================================


class MonthlyAccrualRun(SQLModel):
    target_year: int
    target_month: int


class YearEndCarryoverRun(SQLModel):
    target_year_from: int
    target_year_to: int


class ManualAdjustment(SQLModel):
    employee_id: uuid.UUID
    policy_id: uuid.UUID
    leave_year: int
    delta: Decimal
    note: str = Field(max_length=1024)
