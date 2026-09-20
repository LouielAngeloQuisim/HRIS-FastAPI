"""Phase B4 entities: Payroll, government calculators, integration platform.

Conventions (uniform with Phase 0-2B and b3):
- UUID PKs, snake_case singular table names via ``__tablename__``.
- Uniform soft delete: ``is_deleted`` (NOT NULL DEFAULT false) + ``deleted_at``.
- ``get_datetime_utc`` redefined per-module to match the Phase 0 pattern.
- Government rates are table-driven: bracket rows are admin-updatable data,
  never hardcoded constants in calculator code.
- Financial columns are ``Numeric`` (Decimal) for currency precision.
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
    """Base for str enums that properly integrate with Pydantic v2."""

    def __conform__(self, dialect: Any) -> str:
        return str(self.value)

    @classmethod
    def get_pydantic_core_schema(cls, source_type: type, handler: GetCoreSchemaHandler) -> dict[str, Any]:
        from pydantic import CoreSchema
        return CoreSchema(type="string")  # type: ignore


class ConnectorType(_StrEnum):
    GENERIC_REST = "generic_rest"


class CutoffType(_StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    SEMI_MONTHLY = "semi_monthly"
    MONTHLY = "monthly"


class PayType(_StrEnum):
    MONTHLY = "monthly"
    DAILY = "daily"
    HOURLY = "hourly"


class PayrollRunStatus(_StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    PAID = "paid"
    VOID = "void"


class PayrollAdjustmentType(_StrEnum):
    REGULAR = "regular"
    SUPPLEMENTAL = "supplemental"
    POST_RUN_CORRECTION = "post_run_correction"


class LoanType(_StrEnum):
    SALARY = "salary"
    SSLS = "ssls"
    PAGIBIG = "pagibig"
    OTHER = "other"


# --- Government contribution brackets (B4A.1, table-driven) -----------------------------


class SSSBracket(SQLModel, table=True):
    """SSS contribution bracket row (fixed peso amounts per MSC range).

    Source: SSS Circular 2024-006 (15% total = 10% employer SS + 5% employee SS,
    EC employer-paid ₱10-30, MPF split above ₱20,000 MSC). MSC range ₱5,000-₱35,000.
    Each row holds fixed amounts, mirroring the official published table so admins
    can load new circulars without code changes.
    """

    __tablename__ = "sss_bracket"
    __table_args__ = (Index("ix_sss_bracket_effective_date", "effective_date"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    msc_min: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    msc_max: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    employer_ss: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    employer_ec: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    employer_mpf: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    employee_ss: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    employee_mpf: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    effective_date: date
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PhilHealthBracket(SQLModel, table=True):
    """PhilHealth contribution bracket row (percentage rate with floor/ceiling).

    Source: RA 11223 / Advisory PA2025-0002 (5% total, 2.5% each, basis clamped
    to ₱10,000 floor and ₱100,000 ceiling). ``rate``/``employer_share``/
    ``employee_share`` are percentage values so future circulars can change them.
    """

    __tablename__ = "philhealth_bracket"
    __table_args__ = (Index("ix_philhealth_bracket_effective_date", "effective_date"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    salary_min: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    salary_max: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    rate: Decimal = Field(sa_column=Numeric(6, 3))  # type: ignore
    employer_share: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    employee_share: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    effective_date: date
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PagIBIGBracket(SQLModel, table=True):
    """Pag-IBIG (HDMF) contribution bracket row (percentage rate with MSC cap).

    Source: HDMF Circular 460 (employee 1% when monthly compensation ≤ ₱1,500,
    else 2%; employer 2%; MSC capped at ₱10,000). ``employee_rate``/
    ``employer_rate`` are percentage values.
    """

    __tablename__ = "pagibig_bracket"
    __table_args__ = (Index("ix_pagibig_bracket_effective_date", "effective_date"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    salary_min: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    salary_max: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    employee_rate: Decimal = Field(sa_column=Numeric(6, 3))  # type: ignore
    employer_rate: Decimal = Field(sa_column=Numeric(6, 3))  # type: ignore
    effective_date: date
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class BIRBracket(SQLModel, table=True):
    """BIR withholding tax bracket row (TRAIN, per payment period).

    Source: BIR RR 11-2018 as amended (2023-2025 adjusted brackets). ``period``
    selects the daily/weekly/semi_monthly/monthly table; ``bracket_max`` is
    nullable for the open-ended top bracket. Tax = base_tax + excess × rate.
    """

    __tablename__ = "bir_bracket"
    __table_args__ = (
        Index("ix_bir_bracket_period", "period"),
        Index("ix_bir_bracket_effective_date", "effective_date"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    period: CutoffType = Field(  # type: ignore
        default=CutoffType.MONTHLY,
        sa_type=_EnumAsString(CutoffType, "cutofftype"),
    )
    bracket_min: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    bracket_max: Decimal | None = Field(default=None, sa_column=Numeric(12, 2))  # type: ignore
    base_tax: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    excess_rate: Decimal = Field(sa_column=Numeric(6, 3))  # type: ignore
    effective_date: date
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


# --- Employee salary configuration (B4B.2a) ---------------------------------------------


class EmployeeSalary(SQLModel, table=True):
    """Employee salary configuration with rate and non-taxable allowances.

    Supports multiple rate periods via ``effective_date`` (mid-period rate
    changes pro-rate days before/on the effective date), pay_type
    (monthly/daily/hourly), and the non-taxable allowance set (de minimis caps,
    13th-month exempt portion ≤ ₱90,000/yr).
    """

    __tablename__ = "employee_salary"
    __table_args__ = (
        UniqueConstraint("employee_id", "effective_date", name="uq_employee_salary_employee_date"),
        Index("ix_employee_salary_employee_deleted", "employee_id", "is_deleted"),
        Index("ix_employee_salary_effective_date", "effective_date"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID | None = Field(
        default=None, foreign_key="employee_records.id", ondelete="CASCADE"
    )
    basic_rate: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    currency: str = Field(default="PHP", max_length=3)
    effective_date: date
    pay_type: PayType = Field(  # type: ignore
        default=PayType.MONTHLY,
        sa_type=_EnumAsString(PayType, "paytype"),
    )
    overtime_rate: Decimal = Field(default=Decimal("0.000"), sa_column=Numeric(6, 3))  # type: ignore
    absent_penalty_rate: Decimal = Field(default=Decimal("0.000"), sa_column=Numeric(6, 3))  # type: ignore
    non_taxable_allowance: Decimal = Field(default=Decimal("0.00"), sa_column=Numeric(12, 2))  # type: ignore
    de_minimis_monthly: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    thirteenth_month_exempt_portion: Decimal = Field(
        default=Decimal("90000.00"), sa_column=Numeric(12, 2)  # type: ignore
    )
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


# --- Payroll run lifecycle (B4B.2b/2c) --------------------------------------------------


class PayrollRun(SQLModel, table=True):
    """Payroll run header. Preview computes entries without persisting; generate
    persists entries at status=draft. Approved/paid runs are immutable — void +
    regenerate or a supplemental run is the only correction path. ``is_readonly``
    marks legacy migrated history (Phase B6).
    """

    __tablename__ = "payroll_run"
    __table_args__ = (Index("ix_payroll_run_created_by", "created_by"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    cutoff_type: CutoffType = Field(  # type: ignore
        default=CutoffType.MONTHLY,
        sa_type=_EnumAsString(CutoffType, "cutofftype"),
    )
    date_from: date
    date_to: date
    status: PayrollRunStatus = Field(  # type: ignore
        default=PayrollRunStatus.DRAFT,
        sa_type=_EnumAsString(PayrollRunStatus, "payrollrunstatus"),
    )
    adjustment_type: PayrollAdjustmentType = Field(  # type: ignore
        default=PayrollAdjustmentType.REGULAR,
        sa_type=_EnumAsString(PayrollAdjustmentType, "payrolladjustmenttype"),
    )
    created_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    is_readonly: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PayrollEntry(SQLModel, table=True):
    """Single employee payroll entry with per-employee computation snapshot.

    Stores the effective rate used (``basic_rate`` copy) and the rate window
    (``rate_date_from``/``rate_date_to``) for the mid-period rate-change audit
    trail. Earnings/deductions JSON mirrors the entry columns for line detail.
    """

    __tablename__ = "payroll_entry"
    __table_args__ = (
        UniqueConstraint("payroll_run_id", "employee_id", name="uq_payroll_entry_run_employee"),
        Index("ix_payroll_entry_run_deleted", "payroll_run_id", "is_deleted"),
        Index("ix_payroll_entry_employee_deleted", "employee_id", "is_deleted"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    payroll_run_id: uuid.UUID | None = Field(
        default=None, foreign_key="payroll_run.id", ondelete="CASCADE"
    )
    employee_id: uuid.UUID | None = Field(
        default=None, foreign_key="employee_records.id", ondelete="CASCADE"
    )
    basic_rate: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    rate_date_from: date
    rate_date_to: date
    earnings: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    deductions: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    gross_pay: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    total_deductions: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    net_pay: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    overtime_pay: Decimal = Field(default=Decimal("0.00"), sa_column=Numeric(12, 2))  # type: ignore
    thirteenth_month: Decimal = Field(default=Decimal("0.00"), sa_column=Numeric(12, 2))  # type: ignore
    non_taxable_income: Decimal = Field(default=Decimal("0.00"), sa_column=Numeric(12, 2))  # type: ignore
    taxable_income: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    is_readonly: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


# --- Loans (B4B.2d/2e) ------------------------------------------------------------------


class Loan(SQLModel, table=True):
    """Employee loan tracking with amortization schedules."""

    __tablename__ = "loan"
    __table_args__ = (Index("ix_loan_employee_deleted", "employee_id", "is_deleted"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID | None = Field(
        default=None, foreign_key="employee_records.id", ondelete="CASCADE"
    )
    loan_type: LoanType = Field(  # type: ignore
        default=LoanType.SALARY,
        sa_type=_EnumAsString(LoanType, "loantype"),
    )
    principal: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    balance: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    terms_months: int
    start_date: date
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class LoanAmortization(SQLModel, table=True):
    """Loan amortization payment schedule row."""

    __tablename__ = "loan_amortization"
    __table_args__ = (Index("ix_loan_amortization_loan_deleted", "loan_id", "is_deleted"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    loan_id: uuid.UUID | None = Field(
        default=None, foreign_key="loan.id", ondelete="CASCADE"
    )
    due_date: date
    amount: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    remaining_balance: Decimal = Field(sa_column=Numeric(12, 2))  # type: ignore
    is_paid: bool = Field(default=False)
    paid_date: date | None = Field(default=None)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


# --- Integration platform (B4A.2) -------------------------------------------------------


class IntegrationConfig(SQLModel, table=True):
    """Configuration for third-party REST API integrations."""

    __tablename__ = "integration_config"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255, index=True)
    connector_type: ConnectorType = Field(  # type: ignore
        default=ConnectorType.GENERIC_REST,
        sa_type=_EnumAsString(ConnectorType, "connectortype"),
    )
    api_url: str | None = Field(default=None, max_length=512)
    http_method: str = Field(default="GET", max_length=10)
    headers: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    schedule: str | None = Field(default=None, max_length=128)
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class IntegrationMapping(SQLModel, table=True):
    """Field mapping from source JSON path to target field with transform rule."""

    __tablename__ = "integration_mapping"
    __table_args__ = (
        Index("ix_integration_mapping_config_deleted", "integration_config_id", "is_deleted"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    integration_config_id: uuid.UUID | None = Field(
        default=None, foreign_key="integration_config.id", ondelete="CASCADE"
    )
    source_json_path: str = Field(max_length=512)
    target_field: str = Field(max_length=255)
    transform_rule: str | None = Field(default=None, max_length=1024)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
