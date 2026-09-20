"""Phase B5 — Notification system.

Conventions:
- UUID PK, snake_case table names.
- Uniform soft delete + audit timestamps.
- ``get_datetime_utc`` redefined per module.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import GetCoreSchemaHandler
from sqlalchemy import JSON, DateTime, Index, String, TypeDecorator
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class _StrEnum(str, Enum):
    def __conform__(self, dialect: Any) -> str:
        return str(self.value)

    @classmethod
    def get_pydantic_core_schema(cls, source_type: type[Any], handler: GetCoreSchemaHandler) -> dict[str, Any]:
        from pydantic import CoreSchema
        return CoreSchema(type="string")  # type: ignore


class _EnumAsString(TypeDecorator[str]):
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
        return self.enum_class(value)

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect and dialect.name == "postgresql":
            values = [m.value for m in self.enum_class.__members__.values()]
            return dialect.type_descriptor(
                PGEnum(*values, name=self.db_enum_name, create_constraint=False, validate_strings=True)
            )
        return String()


class NotificationType(_StrEnum):
    LEAVE_SUBMITTED = "leave_submitted"
    LEAVE_APPROVED = "leave_approved"
    LEAVE_REJECTED = "leave_rejected"
    DTR_ADJUSTMENT_SUBMITTED = "dtr_adjustment_submitted"
    DTR_ADJUSTMENT_APPROVED = "dtr_adjustment_approved"
    DTR_ADJUSTMENT_REJECTED = "dtr_adjustment_rejected"
    OVERTIME_APPROVED = "overtime_approved"
    OVERTIME_REJECTED = "overtime_rejected"
    PAYROLL_RUN_GENERATED = "payroll_run_generated"
    PAYROLL_RUN_APPROVED = "payroll_run_approved"
    PAYROLL_RUN_VOIDED = "payroll_run_voided"
    PRE_PAYDAY_CHECK = "pre_payday_check"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    ROLE_CHANGED = "role_changed"
    ACCOUNT_LOCKED = "account_locked"


class Notification(SQLModel, table=True):
    __tablename__ = "notification"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True, ondelete="CASCADE")
    type: NotificationType = Field(sa_type=_EnumAsString(NotificationType, "notificationtype"))  # type: ignore
    title: str = Field(max_length=255)
    body: str = Field(max_length=1024)
    data: dict[str, Any] | None = Field(default=None, sa_type=JSON)
    read_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore

    __table_args__ = (
        Index("ix_notification_user_created", "user_id", "created_at"),
    )
