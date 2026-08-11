"""Centralized exception handlers producing the standard error format."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .responses import (
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
)
from .security import get_request_id


def _error_response(
    *,
    status_code: int,
    error_type: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    request: Request | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = get_request_id(request) if request is not None else None
    body = ErrorResponse(
        detail=message,
        error=ErrorBody(
            type=error_type,
            message=message,
            details=details or [],
        ),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(),
        headers=headers or {},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            ErrorDetail(
                location=".".join(str(p) for p in err.get("loc", [])[:-1]) or None,
                field=".".join(str(p) for p in err.get("loc", [])) or None,
                message=str(err.get("msg", "")),
                type=err.get("type"),
            )
            for err in exc.errors()
        ]
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_type="validation_error",
            message="Request validation failed",
            details=details,
            request=request,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            error_type="http_error",
            message=str(exc.detail),
            request=request,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_handler(request: Request, _exc: IntegrityError) -> JSONResponse:
        """Map DB-level constraint violations to a 409 (design §7.4 / test set D).

        The DB constraint is the real backstop under concurrency; when it fires
        (duplicate unique key, FK violation surfaced as integrity error), return a
        clean 409 rather than an unhandled 500.
        """
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            error_type="conflict",
            message="A record with these unique values already exists.",
            request=request,
        )
