"""Rate-limit dependencies for the authentication endpoints."""

from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status

from app.common.rate_limit import build_key, login_rate_limiter
from app.config.settings import settings

# NB: deliberately no `from __future__ import annotations` here. These
# dependencies are callable class instances, which have no __globals__, so
# FastAPI cannot resolve stringified annotations and would silently downgrade
# `request: Request` to a query parameter.

IdentifierExtractor = Callable[[Request], Awaitable[str | None]]


async def identifier_from_form_username(request: Request) -> str | None:
    """Pull the identifier from an OAuth2 password-grant form body.

    Starlette caches the parsed form on the request, so the route handler's own
    OAuth2PasswordRequestForm dependency reuses this parse rather than trying
    to read an already-consumed stream.
    """
    try:
        form = await request.form()
    except Exception:
        return None
    value = form.get("username")
    return str(value) if value is not None else None


def identifier_from_path(param: str) -> IdentifierExtractor:
    async def _extract(request: Request) -> str | None:
        value = request.path_params.get(param)
        return str(value) if value is not None else None

    return _extract


def identifier_from_json_field(field: str) -> IdentifierExtractor:
    async def _extract(request: Request) -> str | None:
        try:
            payload = await request.json()
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        value = payload.get(field)
        return str(value) if value is not None else None

    return _extract


class RateLimitTicket:
    """Handed to the route so it can clear the counter on success."""

    def __init__(self, *, key: str, enabled: bool) -> None:
        self.key = key
        self.enabled = enabled

    def clear(self) -> None:
        if self.enabled:
            login_rate_limiter.clear(self.key)


class RateLimitGuard:
    """Dependency that enforces the sliding window and exposes a reset hook.

    The guard records the attempt up front so that abandoned or erroring
    requests still count; the route calls ``clear()`` on success so only
    consecutive failures accumulate.
    """

    def __init__(
        self,
        *,
        scope: str,
        identifier: IdentifierExtractor | None = None,
        limit: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        self.scope = scope
        self.identifier = identifier
        self.limit = limit
        self.window_seconds = window_seconds

    @property
    def _limit(self) -> int:
        return self.limit or settings.LOGIN_RATE_LIMIT_ATTEMPTS

    @property
    def _window(self) -> int:
        return self.window_seconds or settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS

    async def __call__(self, request: Request) -> RateLimitTicket:
        client_ip = request.client.host if request.client else None
        identifier = await self.identifier(request) if self.identifier else None
        key = build_key(scope=self.scope, client_ip=client_ip, identifier=identifier)

        if not settings.RATE_LIMIT_ENABLED:
            return RateLimitTicket(key=key, enabled=False)

        result = login_rate_limiter.hit(
            key, limit=self._limit, window_seconds=self._window
        )
        if not result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Too many attempts. Please try again in "
                    f"{result.retry_after} seconds."
                ),
                headers={"Retry-After": str(result.retry_after)},
            )
        return RateLimitTicket(key=key, enabled=True)


login_rate_limit = RateLimitGuard(
    scope="login", identifier=identifier_from_form_username
)
password_recovery_rate_limit = RateLimitGuard(
    scope="password-recovery", identifier=identifier_from_path("email")
)
password_reset_rate_limit = RateLimitGuard(
    scope="password-reset", identifier=identifier_from_json_field("token")
)
