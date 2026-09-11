"""Protocol interfaces for leave domain (mypy isolation).

These protocols isolate app/leave from concrete EmployeeRecords and User models,
preventing mypy from reaching into app/employee and app/user (which have pre-
existing strictness violations).
"""

from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class EmployeeRecordProtocol(Protocol):
    id: UUID
    department_id: UUID | None
    shift_id: UUID | None
    user_id: UUID | None
    is_deleted: bool


@runtime_checkable
class UserProtocol(Protocol):
    id: UUID
    is_superuser: bool
