# HRIS Backend

FastAPI + SQLModel + Alembic backend for the HRIS rewrite. Project rules,
architecture conventions, and current baselines live in
[`../AGENTS.md`](../AGENTS.md) (see §1.5 testing policy and §5 architecture) —
this file is only the practical getting-started guide.

## Requirements

- [Docker](https://www.docker.com/)
- [uv](https://docs.astral.sh/uv/) for Python dependency management
- PostgreSQL runs in Docker Compose. `pyproject.toml` pins Python
  `>=3.10,<4.0`; the production image is `python:3.10` (`backend/Dockerfile`);
  the local dev venv is Python 3.12 (repo-root `.venv` — `backend/` is a uv
  workspace member of the root `pyproject.toml`, so `uv sync` from either
  directory manages that single venv)

## Quick start

From the repo root (or `backend/`):

```console
$ uv sync                        # install dependencies into repo-root .venv
$ source .venv/bin/activate      # from the repo root
```

Editor tip: point your Python interpreter at the repo-root
`.venv/bin/python`.

The full local stack (db + backend + frontend + Adminer + Mailcatcher via
Docker Compose) is described in [`../development.md`](../development.md);
the host-based daily workflow is described in
[`../LOCAL_SETUP.md`](../LOCAL_SETUP.md).

## Where code goes

The backend is organized as **domain packages**, not one-file-per-resource:

- Each domain lives in `app/<domain>/` (e.g. `app/employee/`, `app/leave/`,
  `app/payroll/`) and layers `models.py` / `schemas.py` / `selectors.py` /
  `services.py` / `routes.py`.
- SQLModel models are aggregated in `app/models.py` (Alembic autogenerate
  imports them from there via `alembic/env.py`).
- Routers are aggregated in `app/api.py`. The 16 employee-domain resource
  routers are built by a factory in `app/employee/routes.py`.
- There is **no** `app/crud.py` and **no** `app/api/` package — those were
  upstream-template paths removed during the rewrite. Shared infrastructure
  lives in `app/common/`.

RBAC is enforced per route with `require_permission`; the public-route
allowlist is `app/common/route_policy.py`. See AGENTS.md §5 for the full
conventions and `docs/MAP.md` for the generated route/permission inventory.

## Running tests

The single entry point for "does this actually work" is the repository
verification gate (run from the repo root):

```console
$ bash scripts/verify.sh
```

It runs ruff, mypy, alembic upgrade+drift-check, and pytest against a
throwaway postgres container, then the frontend checks, and prints a
PASS/FAIL summary.

Container-only equivalents (when the stack is already running):

```console
$ docker compose exec backend bash scripts/tests-start.sh        # full suite via pytest
$ docker compose exec backend bash scripts/tests-start.sh -x     # extra pytest args are forwarded
```

Inside `backend/`, `bash scripts/test.sh` runs pytest under `coverage` and
writes `htmlcov/index.html` (there is no coverage threshold gate in CI).

Every change must include its test and a full verification run before being
reported complete — AGENTS.md §1.5.

## Migrations

Migrations live in `backend/alembic/versions/` (not `backend/app/alembic/`).

After changing a SQLModel model, from `backend/`:

```console
$ uv run alembic revision --autogenerate -m "Add column X to Y model"
$ uv run alembic upgrade head
$ uv run alembic check        # proves no model/migration drift
```

The same checks run in `scripts/verify.sh` against a throwaway database, so
drift never reaches a PR. If you work inside the backend container instead,
run the same `alembic` commands there and commit the generated revision.

Production migration policy (never hand-run against prod; deploy via PR +
`scripts/prestart.sh`) is authoritative in
[`../docs/runbooks/migrations.md`](../docs/runbooks/migrations.md).

## Email templates

Templates are in `backend/app/email-templates/` with `src/` (`.mjml` source)
and `build/` (rendered `.html` used by the app). Edit in `src/`, export the
compiled HTML to `build/` (the VS Code MJML extension's *MJML: Export to
HTML* command produces the file), and commit both.

## Lint / format / hooks

Backend lint and format are **ruff** (AGENTS.md §4). A shared
`.pre-commit-config.yaml` exists at the repo root; to run its hooks
manually, from `backend/`:

```console
$ uv run prek run --all-files
```

To have them run automatically on commit: `uv run prek install -f`.
