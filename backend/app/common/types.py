"""Shared typing primitives used across the domain packages.

``AuditedSQLModel`` is the structural contract every soft-delete table in this
codebase satisfies (``id``, ``is_deleted``, the three audit timestamps, and the
``model_validate``/``sqlmodel_update`` inherited from ``SQLModel``). The generic
selector/service helpers are typed against it via the shared ``ModelT`` so a
``type[T]`` parameter actually exposes the columns and methods the helpers
touch, instead of a bare ``type``/``type[SQLModel]`` where they are invisible
to mypy.
"""

from datetime import datetime
from typing import Any, Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel
from typing_extensions import Self


class IDModelMixin(BaseModel):
    id: UUID


class TimestampMixin(BaseModel):
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AuditedSQLModel(Protocol):
    """Everything the generic CRUD helpers assume about a soft-delete model."""

    id: UUID
    is_deleted: bool
    deleted_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def model_validate(
        cls, obj: Any, *, update: dict[str, Any] | None = ...
    ) -> Self: ...

    def sqlmodel_update(
        self, obj: dict[str, Any], *, update: dict[str, Any] | None = ...
    ) -> Self: ...


ModelT = TypeVar("ModelT", bound=AuditedSQLModel)
