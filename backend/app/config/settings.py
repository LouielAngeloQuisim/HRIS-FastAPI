import secrets
import warnings
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


_ENV_FILE = str(Path(__file__).resolve().parents[3] / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # Short-lived access token. Phase 0 decision: 30 minutes (roadmap §2.2 allows
    # 15-60 min). Access tokens are validated by signature alone and cannot be
    # revoked individually, so the window is deliberately small; continuity comes
    # from the refresh token below.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Refresh tokens are stored server-side (hashed) and rotated on every use,
    # which is what makes real logout/revocation possible.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_HOST: str = "http://localhost:5173"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    # --- Engine tuning -----------------------------------------------------
    # pool_pre_ping avoids handing out connections that the server has already
    # dropped; connect_timeout stops a dead DB from hanging requests (and test
    # runs) for the OS-default TCP timeout.
    POSTGRES_POOL_SIZE: int = 5
    POSTGRES_MAX_OVERFLOW: int = 10
    POSTGRES_POOL_RECYCLE_SECONDS: int = 1800
    POSTGRES_CONNECT_TIMEOUT_SECONDS: int = 10
    SQLALCHEMY_ECHO: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    # --- Auth / rate limiting ----------------------------------------------
    # Phase 0 decision: 5 attempts per 15 minutes, keyed on client IP *and* the
    # submitted identifier, so an attacker cannot lock a legitimate user out of
    # their own account by hammering it from a different address.
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 15 * 60
    RATE_LIMIT_ENABLED: bool = True

    # Request bodies are audited; these keys are redacted before anything is
    # written. The legacy system logged raw request bodies including plaintext
    # passwords (roadmap §5) - that must never happen here.
    AUDIT_REDACTED_FIELDS: Annotated[list[str] | str, BeforeValidator(parse_cors)] = [
        "password",
        "new_password",
        "current_password",
        "hashed_password",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "authorization",
        "api_key",
        # Phase 1: 201-file (EmployeeAdditionalRecords) government IDs / PII are
        # sensitive; the legacy system logged these in clear text (roadmap §5).
        "sss_number",
        "tin_number",
        "philhealth_number",
        "pagibig_number",
        "cash_card_number",
        "hmo_account",
        "violations",
        "medical_drug_tests",
        "dependents",
    ]

    # Audit middleware: logs method/path/status/user/duration with redacted
    # bodies. The DB sink (a queryable trail) lands in Phase 5; for Phase 0 the
    # logging sink is authoritative and the DB sink is off by default so no
    # migration is required to boot.
    AUDIT_ENABLED: bool = True
    AUDIT_DB_SINK: bool = False
    AUDIT_BODY_MAX_BYTES: int = 4096

    # Uploaded 201-file documents are stored here (never in the public web root
    # or as DB blobs); only the resulting path is persisted on the record.
    FILE_UPLOAD_DIR: str = "/tmp/hris-uploads"

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


settings = Settings()  # type: ignore
