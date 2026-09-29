# HRIS Development (Docker Compose stack)

This document covers the **full-stack Docker Compose development setup**.
For the host-based daily workflow (run `db` in Docker, backend/frontend on
the host), see [`LOCAL_SETUP.md`](LOCAL_SETUP.md); for the single verification
entry point, see `scripts/verify.sh` (documented in AGENTS.md §1.5).
Production deployment is covered by [`deployment.md`](deployment.md) and the
authoritative runbooks in [`docs/runbooks/`](docs/runbooks/).

## Start the stack

From the repo root (requires a root `.env` — see `backend/env_sample.txt`
for the required variables):

```bash
docker compose up -d       # or `docker compose watch` for live reload
```

The first start can take a minute while the backend waits for the database
and runs prestart migrations. Watch progress with:

```bash
docker compose logs -f backend
```

## Local URLs

| Service | URL | Notes |
| --- | --- | --- |
| Frontend (Nginx serving the Vite build) | <http://localhost:5173> | dev-only compose mapping `5173:80` |
| Backend API | <http://localhost:8000> | OpenAPI at `/api/v1/openapi.json`, Swagger UI at `/docs`, ReDoc at `/redoc` |
| Adminer (DB web UI) | <http://localhost:8080> | server `db`, user/db/password from `.env` |
| Traefik dashboard (local dev Traefik) | <http://localhost:8090> | from `compose.override.yml` (`8090:8080`, `--api.insecure`) |
| Mailcatcher UI | <http://localhost:1080> | catches all outgoing emails; SMTP on host port `1025` |

The dev backend container runs `fastapi run --reload`, so backend edits
reload without a rebuild (source is bind-mounted; see
`compose.override.yml`). The dev database is exposed on host port **5433**
(`5433:5432`) to avoid clashing with a host Postgres on 5432 — this port
difference is a known gotcha, see AGENTS.md §7.

## Running one side on the host instead

Each compose service uses the same port its local dev server would use, so
you can stop the container and run the tool directly:

```bash
docker compose stop frontend
cd frontendv3 && pnpm install && pnpm dev     # Vite dev server

docker compose stop backend
cd backend && uv run fastapi dev app/main.py  # FastAPI dev server with reload
```

## Mailcatcher

Mailcatcher (`schickling/mailcatcher`, defined in `compose.override.yml`) is
a local SMTP server that captures instead of sends. The dev backend is
already configured to use it (`SMTP_HOST: "mailcatcher"`, port 1025). View
captured messages at <http://localhost:1080>. Useful for password-recovery
and notification flows during development.

## Subdomain routing locally (optional)

`compose.override.yml` ships a dev Traefik so host-based routing
(`api.<DOMAIN>` / `dashboard.<DOMAIN>`) can be tested locally. The default
`DOMAIN=localhost` uses the port table above; to emulate the production
subdomain layout, set `DOMAIN` in `.env` to a domain whose subdomains
resolve to 127.0.0.1 and visit `api.<DOMAIN>` / `dashboard.<DOMAIN>`.
Production Traefik runs outside the compose stack — see `deployment.md` and
`docs/runbooks/deploy.md`.

## Pre-commit hooks and linting

Hook definitions live in `.pre-commit-config.yaml` (repo root) and are run
with **prek** (a Rust re-implementation of pre-commit, in the backend dev
dependencies). Current hooks: large-file/TOML/YAML sanity checks, end-of-file
fixer, trailing-whitespace, and **ruff** check/format for Python. Frontend
linting is **eslint + prettier** from `frontendv3/` (no Biome).

Install to run on every commit (from `backend/`):

```bash
uv run prek install -f
```

Run manually over all files (from `backend/`):

```bash
uv run prek run --all-files
```

## Verification

Before claiming any change works, run the repo gate from the root:

```bash
bash scripts/verify.sh
```

See AGENTS.md §1.5 for the mandatory testing policy and
[`docs/feature-development-workflow.md`](docs/feature-development-workflow.md)
for the end-to-end worktree → plan → implement → verify → PR process.
