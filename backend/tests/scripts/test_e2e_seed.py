"""The E2E seed must fail closed outside an explicitly local test database."""

import importlib.util
from pathlib import Path

import pytest

from app.config.settings import settings

spec = importlib.util.spec_from_file_location(
    "seed_e2e", Path(__file__).resolve().parents[2] / "scripts" / "seed_e2e.py"
)
assert spec and spec.loader
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


@pytest.mark.parametrize(
    ("opt_in", "environment", "server"),
    [
        ("false", "local", "127.0.0.1"),
        ("true", "production", "127.0.0.1"),
        ("true", "local", "database.example.com"),
    ],
)
def test_seed_rejects_nonisolated_environment(monkeypatch, opt_in, environment, server):
    monkeypatch.setenv("E2E_SEED_ALLOWED", opt_in)
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    monkeypatch.setattr(settings, "POSTGRES_SERVER", server)
    with pytest.raises(SystemExit, match="explicit opt-in and a local database"):
        seed.main()


def test_seed_fails_immediately_with_actionable_error_when_user_creation_fails(
    monkeypatch,
):
    class EmptySession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setenv("E2E_SEED_ALLOWED", "true")
    monkeypatch.setenv("E2E_USER_EMAIL", "e2e-user-placeholder@example.com")
    monkeypatch.setattr(settings, "ENVIRONMENT", "local")
    monkeypatch.setattr(settings, "POSTGRES_SERVER", "127.0.0.1")
    monkeypatch.setattr(seed, "Session", lambda _engine: EmptySession())
    monkeypatch.setattr(seed, "init_db", lambda _session: None)
    monkeypatch.setattr(seed, "get_user_by_email", lambda **_kwargs: None)

    def fail_create_user(**_kwargs):
        raise OSError("injected database write failure")

    monkeypatch.setattr(seed, "create_user", fail_create_user)

    with pytest.raises(
        RuntimeError,
        match="E2E user seed failed; dependent browser tests were not started: injected database write failure",
    ):
        seed.main()
