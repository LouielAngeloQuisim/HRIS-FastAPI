"""Phase b3 entities: Leave & Holidays (design doc §1.2).

Conventions (uniform with Phase 0-2B):
- UUID PKs, snake_case singular table names via ``__tablename__``.
- Uniform soft delete: ``is_deleted`` (NOT NULL DEFAULT false) + ``deleted_at``.
- ``get_datetime_utc`` redefined per-module to match the Phase 0 pattern.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import GetCoreSchemaHandler
from sqlalchemy import (
    JSON,
    DateTime,
    Index,
    Numeric,
    String,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class _EnumAsString(TypeDecorator[str]):
    """TypeDecorator that stores Python str-enum values as-is (lowercase strings).

    The PostgreSQL ENUM type is created via migration. This decorator ensures
    that when binding, we return the .value (lowercase) not the enum member name
    (uppercase).
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_class: type[Enum], db_enum_name: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.enum_class = enum_class
        self.db_enum_name = db_enum_name

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, Enum):
            return value.value
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, Enum):
            return value
        # Convert string back to enum member
        return self.enum_class(value)

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect and dialect.name == "postgresql":
            values = [m.value for m in self.enum_class.__members__.values()]
            return dialect.type_descriptor(
                PGEnum(*values, name=self.db_enum_name, create_constraint=False, validate_strings=True)
            )
        return String()


class _StrEnum(str, Enum):
    """Base for str enums that properly integrate with Pydantic v2.

    Pydantic v2 can serialize str,Enum types, but we must provide an
    explicit core schema to avoid PydanticSchemaGenerationError.
    """

    def __conform__(self, dialect: Any) -> str:
        return str(self.value)

    @classmethod
    def get_pydantic_core_schema(cls, source_type: type, handler: GetCoreSchemaHandler) -> dict[str, Any]:
        from pydantic import CoreSchema
        return CoreSchema(type="string")  # type: ignore


class LeaveCadence(_StrEnum):
    ANNUAL = "annual"
    MONTHLY = "monthly"


class GenderScope(_StrEnum):
    ALL = "all"
    MALE = "male"
    FEMALE = "female"


class MaritalStatusScope(_StrEnum):
    ALL = "all"
    SINGLE = "single"
    MARRIED = "married"
    WIDOWED = "widowed"
    DIVORCED = "divorced"


class LeaveStatus(_StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class LeaveRequestEventType(_StrEnum):
    CREATED = "created"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    NOOP = "noop"


class LeaveLedgerSource(_StrEnum):
    GRANT = "grant"
    ACCRUAL = "accrual"
    CARRYOVER_IN = "carryover_in"
    CONSUMED = "consumed"
    REVERSAL = "reversal"
    CARRYOVER_OUT = "carryover_out"
    MANUAL_ADJUSTMENT = "manual_adjustment"


class HolidayType(_StrEnum):
    REGULAR = "regular"
    SPECIAL_NON_WORKING = "special_non_working"
    SPECIAL_WORKING = "special_working"
    COMPANY = "company"


class ObserveWeekendAs(_StrEnum):
    PREVIOUS_FRIDAY = "previous_friday"
    NEXT_MONDAY = "next_monday"
    NEAREST_WEEKDAY = "nearest_weekday"


# --- LeavePolicy -------------------------------------------------------------------------


class LeavePolicy(SQLModel, table=True):
    """The configurable leave type. Legacy ``LeaveType``."""

    __tablename__ = "leave_policy"
    __table_args__ = (
        UniqueConstraint("code", name="uq_leave_policy_code"),
        Index("ix_leave_policy_is_active", "is_active"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    calendar_color: str = Field(max_length=7, default="#3B82F6")
    cadence: LeaveCadence = Field(  # type: ignore
        default=LeaveCadence.ANNUAL,
        sa_type=_EnumAsString(LeaveCadence, "leavecadence"),
    )
    annual_entitlement_days: Decimal = Field(default=Decimal("0.00"), sa_column=Numeric(8, 2))  # type: ignore
    prorate_on_hire: bool = Field(default=False)
    carry_over_enabled: bool = Field(default=False)
    carry_over_max_days: Decimal | None = Field(  # type: ignore
        default=None, sa_column=Numeric(8, 2)
    )
    carry_over_expires_on: date | None = Field(default=None)
    is_paid: bool = Field(default=True)
    eligible_departments: list[uuid.UUID] = Field(
        default_factory=list, sa_type=JSON
    )
    gender_scope: GenderScope = Field(  # type: ignore
        default=GenderScope.ALL,
        sa_type=_EnumAsString(GenderScope, "genderscope"),
    )
    marital_status_scope: MaritalStatusScope = Field(  # type: ignore
        default=MaritalStatusScope.ALL,
        sa_type=_EnumAsString(MaritalStatusScope, "maritalstatusscope"),
    )
    is_active: bool = Field(default=True)
    is_system: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


# --- EmployeeLeaveEnrollment ------------------------------------------------------------


class EmployeeLeaveEnrollment(SQLModel, table=True):
    """Per employee, per policy, per year enrollment."""

    __tablename__ = "employee_leave_enrollment"
    __table_args__ = (
        UniqueConstraint("employee_id", "policy_id", "leave_year", name="uq_enrollment_employee_policy_year"),
        Index("ix_enrollment_employee_deleted", "employee_id", "is_deleted"),
        Index("ix_enrollment_policy_deleted", "policy_id", "is_deleted"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID | None = Field(
        default=None, foreign_key="employee_records.id", index=True, ondelete="CASCADE"
    )
    policy_id: uuid.UUID | None = Field(
        default=None, foreign_key="leave_policy.id", index=True, ondelete="CASCADE"
    )
    leave_year: int = Field(default=2026, index=True)
    granted_days: Decimal = Field(  # type: ignore
        default=Decimal("0.00"), sa_column=Numeric(8, 2)
    )
    is_active: bool = Field(default=True)
    is_transferred: bool = Field(default=False)
    transferred_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


# --- LeaveRequest ------------------------------------------------------------------------


class LeaveRequest(SQLModel, table=True):
    """A leave request. Legacy ``EmployeeLeave``."""

    __tablename__ = "leave_request"
    __table_args__ = (
        Index("ix_leave_request_employee_deleted", "employee_id", "is_deleted"),
        Index("ix_leave_request_status_deleted", "status", "is_deleted"),
        Index("ix_leave_request_status_year", "status", "leave_year"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID | None = Field(
        default=None, foreign_key="employee_records.id", index=True, ondelete="CASCADE"
    )
    policy_id: uuid.UUID | None = Field(
        default=None, foreign_key="leave_policy.id", index=True, ondelete="CASCADE"
    )
    enrollment_id: uuid.UUID | None = Field(
        default=None, foreign_key="employee_leave_enrollment.id", index=True, ondelete="SET NULL"
    )
    date_start: date = Field(default=None)
    date_end: date = Field(default=None)
    leave_year: int = Field(default=2026, index=True)
    requested_hours: Decimal | None = Field(  # type: ignore
        default=None, sa_column=Numeric(8, 2)
    )
    total_days_requested: Decimal = Field(  # type: ignore
        default=Decimal("0.00"), sa_column=Numeric(8, 2)
    )
    reason: str | None = Field(default=None, max_length=1024)
    document_ref: str | None = Field(default=None, max_length=255)
    status: LeaveStatus = Field(  # type: ignore
        default=LeaveStatus.PENDING,
        sa_type=_EnumAsString(LeaveStatus, "leavestatus"),
    )
    created_by_user: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", index=True, ondelete="SET NULL"
    )
    approved_by_user: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    approved_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    rejected_by_user: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    rejected_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    cancelled_by_user: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    cancelled_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    decision_note: str | None = Field(default=None, max_length=1024)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


# --- LeaveRequestEvent ------------------------------------------------------------------


class LeaveRequestEvent(SQLModel, table=True):
    """Append-only audit trail for leave request state transitions."""

    __tablename__ = "leave_request_event"
    __table_args__ = (
        Index("ix_leave_event_request", "request_id"),
        Index("ix_leave_event_actor", "actor_user_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    request_id: uuid.UUID = Field(
        default=None, foreign_key="leave_request.id", ondelete="CASCADE"
    )
    event: LeaveRequestEventType = Field(  # type: ignore
        default=LeaveRequestEventType.CREATED,
        sa_type=_EnumAsString(LeaveRequestEventType, "leaverequesteventtype"),
    )
    actor_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    note: str | None = Field(default=None, max_length=1024)
    run_id: str | None = Field(default=None, max_length=64)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


# --- LeaveLedgerEntry -------------------------------------------------------------------


class LeaveLedgerEntry(SQLModel, table=True):
    """Append-only signed-decimal balance entries."""

    __tablename__ = "leave_ledger_entry"
    __table_args__ = (
        Index("ix_ledger_employee_policy_year", "employee_id", "policy_id", "leave_year"),
        Index("ix_ledger_source", "source"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID = Field(
        default=None, foreign_key="employee_records.id", index=True, ondelete="CASCADE"
    )
    policy_id: uuid.UUID = Field(
        default=None, foreign_key="leave_policy.id", index=True, ondelete="CASCADE"
    )
    enrollment_id: uuid.UUID | None = Field(
        default=None, foreign_key="employee_leave_enrollment.id", ondelete="SET NULL"
    )
    leave_year: int = Field(default=2026, index=True)
    source: LeaveLedgerSource = Field(  # type: ignore
        default=LeaveLedgerSource.GRANT,
        sa_type=_EnumAsString(LeaveLedgerSource, "leaveledgersource"),
    )
    amount: Decimal = Field(  # type: ignore
        default=Decimal("0.00"), sa_column=Numeric(8, 2)
    )
    reference: str | None = Field(default=None, max_length=128)
    original_year: int | None = Field(default=None)
    note: str | None = Field(default=None, max_length=1024)
    actor_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


# --- HolidayConfig ----------------------------------------------------------------------


class HolidayConfig(SQLModel, table=True):
    """Holiday template. Legacy ``Holiday``."""

    __tablename__ = "holiday_config"
    __table_args__ = (
        UniqueConstraint("code", name="uq_holiday_config_code"),
        Index("ix_holiday_config_is_active", "is_active"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    name: str = Field(max_length=255)
    month_day: str = Field(max_length=5)  # MM-DD format
    type: HolidayType = Field(  # type: ignore
        default=HolidayType.REGULAR,
        sa_type=_EnumAsString(HolidayType, "holidaytype"),
    )
    region_code: str | None = Field(default=None, max_length=32)
    observe_weekend_as: ObserveWeekendAs | None = Field(  # type: ignore
        default=None,
        sa_type=_EnumAsString(ObserveWeekendAs, "observeweekendas"),
    )
    multiplier_regular: Decimal | None = Field(  # type: ignore
        default=None, sa_column=Numeric(6, 3)
    )
    multiplier_overtime: Decimal | None = Field(  # type: ignore
        default=None, sa_column=Numeric(6, 3)
    )
    is_recurring: bool = Field(default=True)
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


# --- HolidayInstance --------------------------------------------------------------------


class HolidayInstance(SQLModel, table=True):
    """Per-year holiday occurrence (observed date, after weekend rule)."""

    __tablename__ = "holiday_instance"
    __table_args__ = (
        UniqueConstraint("config_id", "observed_date", name="uq_holiday_instance_config_date"),
        Index("ix_holiday_instance_year", "leave_year"),
        Index("ix_holiday_instance_date", "observed_date"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    config_id: uuid.UUID = Field(
        default=None, foreign_key="holiday_config.id", index=True, ondelete="CASCADE"
    )
    observed_date: date = Field(default=None)
    raw_date: date | None = Field(default=None)  # original calendar date before weekend rule
    leave_year: int = Field(default=2026)
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
