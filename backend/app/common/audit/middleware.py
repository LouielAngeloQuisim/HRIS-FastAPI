"""Per-request audit middleware.

Assigns a request id, captures timing, redacts the request body, and emits an
`AuditRecord` to the configured sink. The DB sink is eagerly attempted only
when `AUDIT_DB_SINK` is enabled (Phase 5); otherwise the logging sink is used.
"""

from __future__ import annotations

import time

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.common.audit.redactor import redact_json
from app.common.audit.sink import AuditRecord, get_audit_sink
from app.common.security import REQUEST_ID_HEADER
from app.config.settings import settings


class AuditMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        request_id = request.headers.get(REQUEST_ID_HEADER) or _new_id()
        request.state.request_id = request_id

        content_type = request.headers.get("content-type", "")
        should_capture = settings.AUDIT_ENABLED and "application/json" in content_type

        raw = b""
        if should_capture:
            # Read once; the body is replayed via a cached receive below so the
            # downstream route still receives it (the original receive queue is
            # single-use and would otherwise be drained).
            raw = await request.body()

        start = time.perf_counter()
        status_code = 500
        error = None

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", []).append(
                    (REQUEST_ID_HEADER.encode(), request_id.encode())
                )
            await send(message)

        async def cached_receive() -> dict:
            return {"type": "http.request", "body": raw, "more_body": False}

        try:
            if should_capture:
                await self.app(request.scope, cached_receive, send_wrapper)
            else:
                await self.app(request.scope, receive, send_wrapper)
        except Exception as exc:  # pragma: no cover - safety net
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            record = AuditRecord(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=duration_ms,
                user_id=getattr(request.state, "user_id", None),
                user_email=getattr(request.state, "user_email", None),
                ip_address=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                module=getattr(request.state, "audit_module", None),
                action=getattr(request.state, "audit_action", None),
                redacted_body=redact_json(
                    raw.decode("utf-8", errors="replace"),
                    max_bytes=settings.AUDIT_BODY_MAX_BYTES,
                )
                if should_capture
                else None,
                error=error,
            )
            try:
                get_audit_sink().emit(record)
            except Exception:  # pragma: no cover - never break a response
                pass


def _new_id() -> str:
    import uuid

    return str(uuid.uuid4())


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
