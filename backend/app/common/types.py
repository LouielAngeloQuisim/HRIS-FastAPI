from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel


class IDModelMixin(BaseModel):
    id: UUID


class TimestampMixin(BaseModel):
    created_at: datetime | None = None
    updated_at: datetime | None = None