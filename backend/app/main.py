import logging

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api import api_router
from app.common.audit import AuditMiddleware
from app.common.error_handlers import register_exception_handlers
from app.config.settings import settings


def _configure_audit_logging() -> None:
    audit_logger = logging.getLogger("hris.audit")
    if audit_logger.handlers:
        return
    handler: logging.Handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(handler)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(
        dsn=str(settings.SENTRY_DSN),
        environment=settings.ENVIRONMENT,
        send_default_pii=settings.ENVIRONMENT != "production",
        enable_logs=True,
        traces_sample_rate=1.0 if settings.ENVIRONMENT != "production" else 0.1,
        profile_session_sample_rate=1.0 if settings.ENVIRONMENT != "production" else 0.1,
        profile_lifecycle="trace",
    )

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

_configure_audit_logging()
register_exception_handlers(app)

if settings.AUDIT_ENABLED:
    app.add_middleware(AuditMiddleware)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)
