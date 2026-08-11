"""Phase 1 entities: Employee core + Org structure + Construction/manpower.

Approved design: docs/roadmap/phase1-design.md. Conventions:
- UUID PKs (matches Phase 0 User/Role/Module).
- snake_case singular table names via ``__tablename__``.
- Uniform soft delete: ``is_deleted`` (NOT NULL DEFAULT false) + ``deleted_at``.
  Legacy's three-way ``archived``/``isArchived``/``removed`` is unified here.
- Composite indexes pair ``is_deleted`` with the FK it is filtered alongside
  (see design §7).
- ``get_datetime_utc`` is redefined per-module to match the Phase 0 pattern.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import JSON, DateTime, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class EmployeeStatus(str, Enum):
    """Values taken verbatim from the legacy source's employee_status literals."""

    ACTIVE = "Active"
    RESIGNED = "Resigned"
    TERMINATED = "Terminated"
    ON_LEAVE = "On Leave"


# ---------------------------------------------------------------------------
# 1.1 Employee & HR core
# ---------------------------------------------------------------------------
class EmployeeRecordsBase(SQLModel):
    employee_code: str = Field(min_length=1, max_length=32)
    first_name: str = Field(min_length=1, max_length=255)
    middle_name: str | None = Field(default=None, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    extension: str | None = Field(default=None, max_length=32)
    birthdate: date
    birth_place: str | None = Field(default=None, max_length=255)
    gender: str | None = Field(default=None, max_length=32)
    civil_status: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    zip_code: str | None = Field(default=None, max_length=10)
    area: str | None = Field(default=None, max_length=255)
    present_barangay: str | None = Field(default=None, max_length=255)
    present_city: str | None = Field(default=None, max_length=255)
    same_address: bool | None = Field(default=None)
    permanent_barangay: str | None = Field(default=None, max_length=255)
    permanent_city: str | None = Field(default=None, max_length=255)
    date_hired: date | None = Field(default=None)
    employee_status: EmployeeStatus = EmployeeStatus.ACTIVE
    employment_type: str | None = Field(default=None, max_length=64)
    contract_expiry_date: date | None = Field(default=None)
    date_separated: date | None = Field(default=None)
    probationary_date: date | None = Field(default=None)
    regularization_date: date | None = Field(default=None)
    telephone: str | None = Field(default=None, max_length=32)
    cellphone: str | None = Field(default=None, max_length=32)
    profile_photo_path: str | None = Field(default=None, max_length=512)


class EmployeeRecordsCreate(EmployeeRecordsBase):
    position_id: uuid.UUID | None = Field(default=None)
    division_id: uuid.UUID | None = Field(default=None)
    department_id: uuid.UUID | None = Field(default=None)
    user_id: uuid.UUID | None = Field(default=None)


class EmployeeRecordsUpdate(SQLModel):
    """All optional; position is an FK (design Q3), never a free-text string."""

    employee_code: str | None = Field(default=None, min_length=1, max_length=32)
    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    middle_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, min_length=1, max_length=255)
    extension: str | None = Field(default=None, max_length=32)
    birthdate: date | None = Field(default=None)
    birth_place: str | None = Field(default=None, max_length=255)
    gender: str | None = Field(default=None, max_length=32)
    civil_status: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    zip_code: str | None = Field(default=None, max_length=10)
    area: str | None = Field(default=None, max_length=255)
    present_barangay: str | None = Field(default=None, max_length=255)
    present_city: str | None = Field(default=None, max_length=255)
    same_address: bool | None = Field(default=None)
    permanent_barangay: str | None = Field(default=None, max_length=255)
    permanent_city: str | None = Field(default=None, max_length=255)
    date_hired: date | None = Field(default=None)
    employee_status: EmployeeStatus | None = Field(default=None)
    position_id: uuid.UUID | None = Field(default=None)
    employment_type: str | None = Field(default=None, max_length=64)
    contract_expiry_date: date | None = Field(default=None)
    date_separated: date | None = Field(default=None)
    probationary_date: date | None = Field(default=None)
    regularization_date: date | None = Field(default=None)
    telephone: str | None = Field(default=None, max_length=32)
    cellphone: str | None = Field(default=None, max_length=32)
    profile_photo_path: str | None = Field(default=None, max_length=512)


class EmployeeRecords(EmployeeRecordsBase, table=True):
    __tablename__ = "employee_records"
    __table_args__ = (
        UniqueConstraint("employee_code", name="uq_employee_records_employee_code"),
        Index("ix_employee_records_division_deleted", "division_id", "is_deleted"),
        Index("ix_employee_records_department_deleted", "department_id", "is_deleted"),
        Index("ix_employee_records_status_deleted", "employee_status", "is_deleted"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
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
    division_id: uuid.UUID | None = Field(
        default=None, foreign_key="division.id", index=True, ondelete="SET NULL"
    )
    department_id: uuid.UUID | None = Field(
        default=None, foreign_key="department.id", index=True, ondelete="SET NULL"
    )
    position_id: uuid.UUID | None = Field(
        default=None, foreign_key="position.id", index=True, ondelete="SET NULL"
    )
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", index=True, ondelete="SET NULL"
    )


class EmployeeRecordsPublic(EmployeeRecordsBase):
    id: uuid.UUID
    position_id: uuid.UUID | None = None
    division_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    is_deleted: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EmployeeRecordsList(SQLModel):
    data: list[EmployeeRecordsPublic]
    count: int


class EmployeeAdditionalRecords(SQLModel, table=True):
    """201-file annex. JSON blobs stay JSON (native JSONB), not legacy ARRAY."""

    __tablename__ = "employee_additional_records"
    __table_args__ = (
        UniqueConstraint("employee_id", name="uq_employee_additional_records_employee_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID = Field(
        default=None, foreign_key="employee_records.id", index=True, ondelete="CASCADE"
    )
    employment_history: dict | None = Field(default=None, sa_type=JSON)  # type: ignore
    past_employment_record: dict | None = Field(default=None, sa_type=JSON)  # type: ignore
    educational_background: dict | None = Field(default=None, sa_type=JSON)  # type: ignore
    seminars_trainings: dict | None = Field(default=None, sa_type=JSON)  # type: ignore
    assessments_exams: dict | None = Field(default=None, sa_type=JSON)  # type: ignore
    skills: dict | None = Field(default=None, sa_type=JSON)  # type: ignore
    awards: dict | None = Field(default=None, sa_type=JSON)  # type: ignore
    licenses: dict | None = Field(default=None, sa_type=JSON)  # type: ignore
    dependents: dict | None = Field(default=None, sa_type=JSON)  # type: ignore
    violations: dict | None = Field(default=None, sa_type=JSON)  # type: ignore
    medical_drug_tests: dict | None = Field(default=None, sa_type=JSON)  # type: ignore
    school_graduated: str | None = Field(default=None, max_length=255)
    course: str | None = Field(default=None, max_length=255)
    career_band_level: str | None = Field(default=None, max_length=255)
    career_global_grade: str | None = Field(default=None, max_length=255)
    cash_card_number: str | None = Field(default=None, max_length=255)
    hmo_account: str | None = Field(default=None, max_length=255)
    sss_number: str | None = Field(default=None, max_length=255)
    philhealth_number: str | None = Field(default=None, max_length=255)
    pagibig_number: str | None = Field(default=None, max_length=255)
    tin_number: str | None = Field(default=None, max_length=255)
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


class EmployeeAttachments(SQLModel, table=True):
    """Uploaded 201-file documents. Only paths are stored (never blobs)."""

    __tablename__ = "employee_attachments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID = Field(
        default=None, foreign_key="employee_records.id", index=True, ondelete="CASCADE"
    )
    type: str | None = Field(default=None, max_length=64)
    attachment_name: str | None = Field(default=None, max_length=255)
    attachment_size: int | None = Field(default=None)
    file_path: str | None = Field(default=None, max_length=512)
    original_file_name: str | None = Field(default=None, max_length=255)
    date_uploaded: datetime | None = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)  # type: ignore
    )
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)  # type: ignore
    )


# ---------------------------------------------------------------------------
# 1.2 Org structure
# ---------------------------------------------------------------------------
class Division(SQLModel, table=True):
    __tablename__ = "division"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    director_id: uuid.UUID | None = Field(
        default=None, foreign_key="employee_records.id", index=True, ondelete="SET NULL"
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


class Department(SQLModel, table=True):
    __tablename__ = "department"
    __table_args__ = (Index("ix_department_division_deleted", "division_id", "is_deleted"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    division_id: uuid.UUID = Field(
        default=None, foreign_key="division.id", index=True, ondelete="CASCADE"
    )
    manager_id: uuid.UUID | None = Field(
        default=None, foreign_key="employee_records.id", index=True, ondelete="SET NULL"
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


class Subdivision(SQLModel, table=True):
    """Top of the construction location tree (Subdivision -> Phase -> Blocks)."""

    __tablename__ = "subdivision"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    subdivision_code: str = Field(max_length=32, unique=True, index=True)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    location: str = Field(max_length=255)
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


class Position(SQLModel, table=True):
    __tablename__ = "position"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    title: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    department_id: uuid.UUID | None = Field(
        default=None, foreign_key="department.id", index=True, ondelete="SET NULL"
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


# ---------------------------------------------------------------------------
# 1.3 Construction / manpower domain
# ---------------------------------------------------------------------------
class ProjectType(SQLModel, table=True):
    """Lookup created in Phase 1 (design Q6). Legacy referenced it but never used it."""

    __tablename__ = "project_type"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    name: str = Field(max_length=255)
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


class Project(SQLModel, table=True):
    __tablename__ = "project"
    __table_args__ = (
        Index("ix_project_subdivision_deleted", "subdivision_id", "is_deleted"),
        Index("ix_project_project_type_deleted", "project_type_id", "is_deleted"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    subdivision_id: uuid.UUID = Field(
        default=None, foreign_key="subdivision.id", index=True, ondelete="CASCADE"
    )
    project_type_id: uuid.UUID | None = Field(
        default=None, foreign_key="project_type.id", index=True, ondelete="SET NULL"
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


class Phase(SQLModel, table=True):
    __tablename__ = "phase"
    __table_args__ = (Index("ix_phase_subdivision_deleted", "subdivision_id", "is_deleted"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    name: str = Field(max_length=255)
    subdivision_id: uuid.UUID = Field(
        default=None, foreign_key="subdivision.id", index=True, ondelete="CASCADE"
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


class Blocks(SQLModel, table=True):
    """Soft-deleted in Phase 1 (design Q7); legacy had none and hard-deleted."""

    __tablename__ = "blocks"
    __table_args__ = (Index("ix_blocks_phase_deleted", "phase_id", "is_deleted"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    block_name: str = Field(max_length=255)
    phase_id: uuid.UUID = Field(
        default=None, foreign_key="phase.id", index=True, ondelete="CASCADE"
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


class Lots(SQLModel, table=True):
    """Soft-deleted in Phase 1 (design Q7). `category_id` unique (1:1 Category)."""

    __tablename__ = "lots"
    __table_args__ = (
        Index("ix_lots_blocks_deleted", "blocks_id", "is_deleted"),
        UniqueConstraint("category_id", name="uq_lots_category_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    lot_num: int | None = Field(default=None)
    lot_name: str | None = Field(default=None, max_length=64)
    blocks_id: uuid.UUID = Field(
        default=None, foreign_key="blocks.id", index=True, ondelete="CASCADE"
    )
    category_id: uuid.UUID | None = Field(
        default=None, foreign_key="category.id", index=True, ondelete="SET NULL"
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


class Category(SQLModel, table=True):
    __tablename__ = "category"
    __table_args__ = (
        Index("ix_category_project_deleted", "project_id", "is_deleted"),
        Index("ix_category_phase_deleted", "phase_id", "is_deleted"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    description: str | None = Field(default=None, max_length=1024)
    location: str | None = Field(default=None, max_length=255)
    is_overhead: bool | None = Field(default=None)
    project_id: uuid.UUID = Field(
        default=None, foreign_key="project.id", index=True, ondelete="CASCADE"
    )
    model_id: uuid.UUID | None = Field(
        default=None, foreign_key="model.id", index=True, ondelete="SET NULL"
    )
    phase_id: uuid.UUID = Field(
        default=None, foreign_key="phase.id", index=True, ondelete="CASCADE"
    )
    blocks_id: uuid.UUID | None = Field(
        default=None, foreign_key="blocks.id", index=True, ondelete="SET NULL"
    )
    owner_id: uuid.UUID | None = Field(
        default=None, foreign_key="owner.id", index=True, ondelete="SET NULL"
    )
    lot_id: uuid.UUID | None = Field(
        default=None, foreign_key="lots.id", index=True, unique=True, ondelete="SET NULL"
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


class Model(SQLModel, table=True):
    __tablename__ = "model"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    model_type_id: uuid.UUID | None = Field(
        default=None, foreign_key="model_types.id", index=True, ondelete="SET NULL"
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


class ModelTypes(SQLModel, table=True):
    __tablename__ = "model_types"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str | None = Field(default=None, max_length=255)
    code: str = Field(max_length=32, unique=True, index=True)
    additional_options: bool | None = Field(default=None)
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


class Owner(SQLModel, table=True):
    """Buyer. Ownership is mediated by Category (design Q8 / Point 3): this table
    carries only denormalised lot_no/block display strings, NOT FKs to Lots/Blocks."""

    __tablename__ = "owner"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    lot_no: str | None = Field(default=None, max_length=32)
    block: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    contact_no: str | None = Field(default=None, max_length=32)
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


class EmployeeProjects(SQLModel, table=True):
    __tablename__ = "employee_projects"
    __table_args__ = (
        Index("ix_employee_projects_project_deleted", "project_id", "is_deleted"),
        Index("ix_employee_projects_employee_deleted", "employee_id", "is_deleted"),
        UniqueConstraint(
            "employee_id", "project_id", name="uq_employee_projects_employee_project"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID = Field(
        default=None, foreign_key="employee_records.id", index=True, ondelete="CASCADE"
    )
    project_id: uuid.UUID = Field(
        default=None, foreign_key="project.id", index=True, ondelete="CASCADE"
    )
    date: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)  # type: ignore
    )
    rendered_hours: int | None = Field(default=None)
    task: str | None = Field(default=None, max_length=512)
    is_assigned: bool | None = Field(default=None)
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


class EmpTask(SQLModel, table=True):
    __tablename__ = "emp_task"
    __table_args__ = (Index("ix_emp_task_emp_project_deleted", "emp_project_id", "is_deleted"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    emp_project_id: uuid.UUID = Field(
        default=None, foreign_key="employee_projects.id", index=True, ondelete="CASCADE"
    )
    task_desc: str | None = Field(default=None, max_length=512)
    rendered_hours: int | None = Field(default=None)
    assigned_hours: Decimal | None = Field(default=None, max_digits=6, decimal_places=2)
    date: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)  # type: ignore
    )
    approved: bool | None = Field(default=None)
    is_adjusted: bool | None = Field(default=None)
    # Phase 2 wires this to worker_logs. No FK is declared yet because the
    # worker_logs table does not exist until Phase 2; it is a plain nullable
    # UUID placeholder for now.
    worker_logs_id: uuid.UUID | None = Field(default=None, index=True)
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
