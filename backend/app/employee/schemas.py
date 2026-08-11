"""Re-export shim for Phase 1 schemas, mirroring app/item/schemas.py.

The table models are declared in app/employee/models.py; this module re-exports
them plus the request/response DTOs used by the Phase 1 routes.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlmodel import Field, SQLModel

from app.employee.models import (
    Blocks,
    Category,
    Department,
    Division,
    EmployeeAdditionalRecords,
    EmployeeAttachments,
    EmployeeProjects,
    EmployeeRecords,
    EmployeeRecordsCreate,
    EmployeeRecordsList,
    EmployeeRecordsPublic,
    EmployeeRecordsUpdate,
    EmployeeStatus,
    EmpTask,
    Lots,
    Model,
    ModelTypes,
    Owner,
    Phase,
    Position,
    Project,
    ProjectType,
    Subdivision,
)

__all__ = [
    "EmployeeRecords",
    "EmployeeRecordsCreate",
    "EmployeeRecordsUpdate",
    "EmployeeRecordsPublic",
    "EmployeeRecordsList",
    "EmployeeAdditionalRecords",
    "EmployeeAttachments",
    "Division",
    "Department",
    "Subdivision",
    "Position",
    "ProjectType",
    "Project",
    "Phase",
    "Blocks",
    "Lots",
    "Category",
    "Model",
    "ModelTypes",
    "Owner",
    "EmployeeProjects",
    "EmpTask",
    "EmployeeStatus",
]


# ---------------------------------------------------------------------------
# EmployeeAdditionalRecords (201-file annex; one row per employee)
# ---------------------------------------------------------------------------
class EmployeeAdditionalRecordsUpdate(SQLModel):
    employment_history: dict | None = None
    past_employment_record: dict | None = None
    educational_background: dict | None = None
    seminars_trainings: dict | None = None
    assessments_exams: dict | None = None
    skills: dict | None = None
    awards: dict | None = None
    licenses: dict | None = None
    dependents: dict | None = None
    violations: dict | None = None
    medical_drug_tests: dict | None = None
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


class EmployeeAdditionalRecordsPublic(SQLModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employment_history: dict | None = None
    past_employment_record: dict | None = None
    educational_background: dict | None = None
    seminars_trainings: dict | None = None
    assessments_exams: dict | None = None
    skills: dict | None = None
    awards: dict | None = None
    licenses: dict | None = None
    dependents: dict | None = None
    violations: dict | None = None
    medical_drug_tests: dict | None = None
    school_graduated: str | None = None
    course: str | None = None
    career_band_level: str | None = None
    career_global_grade: str | None = None
    cash_card_number: str | None = None
    hmo_account: str | None = None
    sss_number: str | None = None
    philhealth_number: str | None = None
    pagibig_number: str | None = None
    tin_number: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# EmployeeAttachments (201-file documents; only paths stored in DB)
# ---------------------------------------------------------------------------
class EmployeeAttachmentsCreate(SQLModel):
    type: str | None = Field(default=None, max_length=64)
    attachment_name: str | None = Field(default=None, max_length=255)
    original_file_name: str | None = Field(default=None, max_length=255)


class EmployeeAttachmentsPublic(SQLModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    type: str | None = None
    attachment_name: str | None = None
    attachment_size: int | None = None
    file_path: str | None = None
    original_file_name: str | None = None
    date_uploaded: datetime | None = None


class EmployeeAttachmentsList(SQLModel):
    data: list[EmployeeAttachmentsPublic]
    count: int


# ---------------------------------------------------------------------------
# Division
# ---------------------------------------------------------------------------
class DivisionCreate(SQLModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    director_id: uuid.UUID | None = None


class DivisionUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    director_id: uuid.UUID | None = None


class DivisionPublic(SQLModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    director_id: uuid.UUID | None = None
    is_deleted: bool
    created_at: datetime | None = None


class DivisionList(SQLModel):
    data: list[DivisionPublic]
    count: int


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------
class DepartmentCreate(SQLModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    division_id: uuid.UUID
    manager_id: uuid.UUID | None = None


class DepartmentUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    division_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None


class DepartmentPublic(SQLModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    division_id: uuid.UUID
    manager_id: uuid.UUID | None = None
    is_deleted: bool
    created_at: datetime | None = None


class DepartmentList(SQLModel):
    data: list[DepartmentPublic]
    count: int


# ---------------------------------------------------------------------------
# Subdivision
# ---------------------------------------------------------------------------
class SubdivisionCreate(SQLModel):
    subdivision_code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    location: str = Field(min_length=1, max_length=255)


class SubdivisionUpdate(SQLModel):
    subdivision_code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    location: str | None = Field(default=None, min_length=1, max_length=255)


class SubdivisionPublic(SQLModel):
    id: uuid.UUID
    subdivision_code: str
    name: str
    description: str | None = None
    location: str
    is_deleted: bool
    created_at: datetime | None = None


class SubdivisionList(SQLModel):
    data: list[SubdivisionPublic]
    count: int


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------
class PositionCreate(SQLModel):
    code: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    department_id: uuid.UUID | None = None


class PositionUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    department_id: uuid.UUID | None = None


class PositionPublic(SQLModel):
    id: uuid.UUID
    code: str
    title: str
    description: str | None = None
    department_id: uuid.UUID | None = None
    is_deleted: bool
    created_at: datetime | None = None


class PositionList(SQLModel):
    data: list[PositionPublic]
    count: int


# ---------------------------------------------------------------------------
# ProjectType
# ---------------------------------------------------------------------------
class ProjectTypeCreate(SQLModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)


class ProjectTypeUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)


class ProjectTypePublic(SQLModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    is_deleted: bool
    created_at: datetime | None = None


class ProjectTypeList(SQLModel):
    data: list[ProjectTypePublic]
    count: int


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------
class ProjectCreate(SQLModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    subdivision_id: uuid.UUID
    project_type_id: uuid.UUID | None = None


class ProjectUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    subdivision_id: uuid.UUID | None = None
    project_type_id: uuid.UUID | None = None


class ProjectPublic(SQLModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    subdivision_id: uuid.UUID
    project_type_id: uuid.UUID | None = None
    is_deleted: bool
    created_at: datetime | None = None


class ProjectList(SQLModel):
    data: list[ProjectPublic]
    count: int


# ---------------------------------------------------------------------------
# Phase
# ---------------------------------------------------------------------------
class PhaseCreate(SQLModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    subdivision_id: uuid.UUID


class PhaseUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    subdivision_id: uuid.UUID | None = None


class PhasePublic(SQLModel):
    id: uuid.UUID
    code: str
    name: str
    subdivision_id: uuid.UUID
    is_deleted: bool
    created_at: datetime | None = None


class PhaseList(SQLModel):
    data: list[PhasePublic]
    count: int


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------
class BlocksCreate(SQLModel):
    block_name: str = Field(min_length=1, max_length=255)
    phase_id: uuid.UUID


class BlocksUpdate(SQLModel):
    block_name: str | None = Field(default=None, min_length=1, max_length=255)
    phase_id: uuid.UUID | None = None


class BlocksPublic(SQLModel):
    id: uuid.UUID
    block_name: str
    phase_id: uuid.UUID
    is_deleted: bool
    created_at: datetime | None = None


class BlocksList(SQLModel):
    data: list[BlocksPublic]
    count: int


# ---------------------------------------------------------------------------
# Lots
# ---------------------------------------------------------------------------
class LotsCreate(SQLModel):
    lot_num: int | None = None
    lot_name: str | None = Field(default=None, max_length=64)
    blocks_id: uuid.UUID
    category_id: uuid.UUID | None = None


class LotsUpdate(SQLModel):
    lot_num: int | None = None
    lot_name: str | None = Field(default=None, max_length=64)
    blocks_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None


class LotsPublic(SQLModel):
    id: uuid.UUID
    lot_num: int | None = None
    lot_name: str | None = None
    blocks_id: uuid.UUID
    category_id: uuid.UUID | None = None
    is_deleted: bool
    created_at: datetime | None = None


class LotsList(SQLModel):
    data: list[LotsPublic]
    count: int


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------
class CategoryCreate(SQLModel):
    code: str = Field(min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=1024)
    location: str | None = Field(default=None, max_length=255)
    is_overhead: bool | None = None
    project_id: uuid.UUID
    model_id: uuid.UUID | None = None
    phase_id: uuid.UUID
    blocks_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    lot_id: uuid.UUID | None = None


class CategoryUpdate(SQLModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=1024)
    location: str | None = Field(default=None, max_length=255)
    is_overhead: bool | None = None
    project_id: uuid.UUID | None = None
    model_id: uuid.UUID | None = None
    phase_id: uuid.UUID | None = None
    blocks_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    lot_id: uuid.UUID | None = None


class CategoryPublic(SQLModel):
    id: uuid.UUID
    code: str
    description: str | None = None
    location: str | None = None
    is_overhead: bool | None = None
    project_id: uuid.UUID
    model_id: uuid.UUID | None = None
    phase_id: uuid.UUID
    blocks_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    lot_id: uuid.UUID | None = None
    is_deleted: bool
    created_at: datetime | None = None


class CategoryList(SQLModel):
    data: list[CategoryPublic]
    count: int


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
class ModelCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    model_type_id: uuid.UUID | None = None


class ModelUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    model_type_id: uuid.UUID | None = None


class ModelPublic(SQLModel):
    id: uuid.UUID
    name: str
    model_type_id: uuid.UUID | None = None
    is_deleted: bool
    created_at: datetime | None = None


class ModelList(SQLModel):
    data: list[ModelPublic]
    count: int


# ---------------------------------------------------------------------------
# ModelTypes
# ---------------------------------------------------------------------------
class ModelTypesCreate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    code: str = Field(min_length=1, max_length=32)
    additional_options: bool | None = None


class ModelTypesUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    additional_options: bool | None = None


class ModelTypesPublic(SQLModel):
    id: uuid.UUID
    name: str | None = None
    code: str
    additional_options: bool | None = None
    is_deleted: bool
    created_at: datetime | None = None


class ModelTypesList(SQLModel):
    data: list[ModelTypesPublic]
    count: int


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------
class OwnerCreate(SQLModel):
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    lot_no: str | None = Field(default=None, max_length=32)
    block: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    contact_no: str | None = Field(default=None, max_length=32)


class OwnerUpdate(SQLModel):
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    lot_no: str | None = Field(default=None, max_length=32)
    block: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    contact_no: str | None = Field(default=None, max_length=32)


class OwnerPublic(SQLModel):
    id: uuid.UUID
    first_name: str | None = None
    last_name: str | None = None
    lot_no: str | None = None
    block: str | None = None
    email: str | None = None
    contact_no: str | None = None
    is_deleted: bool
    created_at: datetime | None = None


class OwnerList(SQLModel):
    data: list[OwnerPublic]
    count: int


# ---------------------------------------------------------------------------
# EmployeeProjects
# ---------------------------------------------------------------------------
class EmployeeProjectsCreate(SQLModel):
    employee_id: uuid.UUID
    project_id: uuid.UUID
    date: datetime | None = None
    rendered_hours: int | None = None
    task: str | None = Field(default=None, max_length=512)
    is_assigned: bool | None = None


class EmployeeProjectsUpdate(SQLModel):
    date: datetime | None = None
    rendered_hours: int | None = None
    task: str | None = Field(default=None, max_length=512)
    is_assigned: bool | None = None


class EmployeeProjectsPublic(SQLModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    project_id: uuid.UUID
    date: datetime | None = None
    rendered_hours: int | None = None
    task: str | None = None
    is_assigned: bool | None = None
    is_deleted: bool
    created_at: datetime | None = None


class EmployeeProjectsList(SQLModel):
    data: list[EmployeeProjectsPublic]
    count: int


# ---------------------------------------------------------------------------
# EmpTask
# ---------------------------------------------------------------------------
class EmpTaskCreate(SQLModel):
    emp_project_id: uuid.UUID
    task_desc: str | None = Field(default=None, max_length=512)
    rendered_hours: int | None = None
    assigned_hours: Decimal | None = Field(default=None, max_digits=6, decimal_places=2)
    date: datetime | None = None
    approved: bool | None = None
    is_adjusted: bool | None = None


class EmpTaskUpdate(SQLModel):
    task_desc: str | None = Field(default=None, max_length=512)
    rendered_hours: int | None = None
    assigned_hours: Decimal | None = Field(default=None, max_digits=6, decimal_places=2)
    date: datetime | None = None
    approved: bool | None = None
    is_adjusted: bool | None = None


class EmpTaskPublic(SQLModel):
    id: uuid.UUID
    emp_project_id: uuid.UUID
    task_desc: str | None = None
    rendered_hours: int | None = None
    assigned_hours: Decimal | None = None
    date: datetime | None = None
    approved: bool | None = None
    is_adjusted: bool | None = None
    is_deleted: bool
    created_at: datetime | None = None


class EmpTaskList(SQLModel):
    data: list[EmpTaskPublic]
    count: int
