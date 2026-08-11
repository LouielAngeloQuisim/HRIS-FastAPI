"""Phase 0 / Item 1 - scaffold foundation.

Covers the settings surface, the Postgres engine configuration, and the
Alembic wiring that the rest of Phase 0 is built on.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlmodel import SQLModel

from app.config.database import ENGINE_CONNECT_ARGS, engine
from app.config.settings import settings


class TestSettings:
    def test_access_token_expiry_is_short_lived(self) -> None:
        """Roadmap §2.2 requires 15-60 min; Phase 0 decision was 30."""
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
        assert 15 <= settings.ACCESS_TOKEN_EXPIRE_MINUTES <= 60

    def test_refresh_token_expiry_configured(self) -> None:
        assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7

    def test_rate_limit_settings_present(self) -> None:
        assert settings.LOGIN_RATE_LIMIT_ATTEMPTS == 5
        assert settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS == 15 * 60

    def test_password_fields_are_marked_for_redaction(self) -> None:
        """The legacy system wrote plaintext passwords into the audit table."""
        redacted = {f.lower() for f in settings.AUDIT_REDACTED_FIELDS}
        for field in ("password", "new_password", "current_password"):
            assert field in redacted

    def test_database_uri_targets_postgres(self) -> None:
        assert str(settings.SQLALCHEMY_DATABASE_URI).startswith(
            "postgresql+psycopg://"
        )


class TestEngine:
    def test_engine_uses_pre_ping(self) -> None:
        """Stops the pool handing out connections the server already dropped."""
        assert engine.pool._pre_ping is True

    def test_engine_pool_sized_from_settings(self) -> None:
        assert engine.pool.size() == settings.POSTGRES_POOL_SIZE

    def test_engine_has_connect_timeout(self) -> None:
        """A dead DB should fail fast rather than hang for the TCP default."""
        assert (
            ENGINE_CONNECT_ARGS["connect_timeout"]
            == settings.POSTGRES_CONNECT_TIMEOUT_SECONDS
        )

    def test_engine_actually_connects(self) -> None:
        """Proves the configured connect args are accepted by the driver."""
        with engine.connect() as connection:
            assert connection.execute(text("select 1")).scalar() == 1


class TestAlembicWiring:
    def test_registry_exposes_all_tables(self) -> None:
        """app/models.py is the single import point Alembic relies on."""
        import app.models  # noqa: F401

        tables = set(SQLModel.metadata.tables)
        assert {"user", "item"} <= tables

    def test_no_pending_schema_drift(self) -> None:
        """The live schema must match the models.

        Guards against a model being added without a migration, which would
        otherwise only surface as a runtime error in production.
        """
        import app.models  # noqa: F401

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            diff = compare_metadata(context, SQLModel.metadata)

        assert diff == [], f"Model/migration drift detected: {diff}"
