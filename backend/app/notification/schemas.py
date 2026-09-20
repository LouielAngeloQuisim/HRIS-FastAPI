"""Request/response DTOs for the notification domain (Phase B5)."""

import uuid
from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel

from app.notification.models import NotificationType


class NotificationCreate(SQLModel):
    user_id: uuid.UUID | None = None
    type: NotificationType
    title: str = Field(max_length=255)
    body: str = Field(max_length=1024)
    data: dict[str, Any] | None = None


class NotificationUpdate(SQLModel):
    read_at: datetime | None = None


class NotificationPublic(NotificationCreate):
    id: uuid.UUID
    read_at: datetime | None = None
    is_deleted: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NotificationList(SQLModel):
    data: list[NotificationPublic]
    count: int
