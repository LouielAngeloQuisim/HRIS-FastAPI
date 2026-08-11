"""Base response envelope and error format.

Phase 0 establishes the shapes; later phases adopt them as each resource is
built. The error format is deliberately *additive* over FastAPI's default:
`detail` is preserved so existing clients and tests keep working, with the
structured `error` object and `request_id` alongside it.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Meta(BaseModel):
    """Pagination metadata returned with list responses."""

    total: int = Field(description="Total rows matching the query")
    skip: int = Field(description="Rows skipped")
    limit: int = Field(description="Maximum rows returned")
    count: int = Field(description="Rows in this page")
    has_more: bool = Field(description="Whether further rows exist")

    @classmethod
    def build(cls, *, total: int, skip: int, limit: int, count: int) -> "Meta":
        return cls(
            total=total,
            skip=skip,
            limit=limit,
            count=count,
            has_more=(skip + count) < total,
        )


class ResponseModel(BaseModel, Generic[T]):
    """Standard success envelope."""

    success: bool = True
    data: T
    message: str | None = None
    meta: Meta | None = None
    request_id: str | None = None


class ErrorDetail(BaseModel):
    """A single field-level problem, used for validation failures."""

    location: str | None = None
    field: str | None = None
    message: str
    type: str | None = None


class ErrorBody(BaseModel):
    type: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Standard failure envelope.

    `detail` duplicates `error.message` so that the response stays
    drop-in-compatible with FastAPI's default error shape.
    """

    success: bool = False
    detail: str
    error: ErrorBody
    request_id: str | None = None
