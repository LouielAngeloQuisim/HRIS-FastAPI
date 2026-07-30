# Local Development Setup

This doc describes the exact local development workflow for this project based on its actual configuration.

---

## Prerequisites

- **Docker Desktop** installed and running
- **Node.js and pnpm** installed
- **uv** installed for Python dependency management
- **VS Code** with the Python and Pylance extensions

---

## Environment Configuration

There is exactly **one `.env` file**, located at the **project root** (not inside `backend/`). Both Docker Compose and the local backend (via Pydantic Settings reading `../.env`) load from this same file.

The file is git-ignored. If you're starting fresh, copy it from an existing working `.env` or create it from scratch. There is no committed `.env.example`.

### Key variables the backend requires (from `backend/app/core/config.py`)

```
DOMAIN=localhost
FRONTEND_HOST=http://localhost:5174
ENVIRONMENT=local
PROJECT_NAME=HRIS
BACKEND_CORS_ORIGINS="http://localhost,http://localhost:5173,..."
SECRET_KEY=<your-secret>
FIRST_SUPERUSER=<your-email>
FIRST_SUPERUSER_PASSWORD=<your-password>

# Postgres
POSTGRES_SERVER=localhost
POSTGRES_PORT=5433
POSTGRES_DB=app
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your-db-password>

# Email (optional for local dev)
SMTP_HOST=
SMTP_USER=
SMTP_PASSWORD=
EMAILS_FROM_EMAIL=info@example.com
SMTP_TLS=True
SMTP_SSL=False
SMTP_PORT=587
```

> **Note:** `compose.yml` `env_file: .env` plus `${VAR?Variable not set}` guards mean several variables must be present or Compose will fail to start. Ensure at minimum `DOMAIN`, `POSTGRES_USER`, `POSTGRES_DASSWORD`, `POSTGRES_DB`, `SECRET_KEY`, `FRONTEND_HOST` are set.

---

## Known Gotchas

### 1. Host Postgres port conflict

If a native/local Postgres installation already exists on the host machine (e.g. via Laragon, XAMPP, or a direct Windows install) on port 5432, Docker's Postgres container will silently fail to bind that port — the container starts but shows no port mapping in `docker compose ps`, with no obvious error.

**Fix:** map Docker's Postgres to a different host port (e.g. `5433:5432`) in `compose.override.yml`, and update `POSTGRES_PORT` in `.env` to match. This project's `compose.override.yml` already uses `5433:5432` for `db`, so `POSTGRES_PORT` in `.env` should be `5433`.

### 2. Docker Compose `$` variable substitution

Docker Compose interprets `$` in `.env` values as variable substitution. Any password or secret containing `$` must be escaped as `$$` in `.env` for Docker Compose — but note this means the actual runtime value inside the container differs from what's literally written unless escaped correctly.

This project's `.env` has `POSTGRES_PASSWORD=p@$w0rd`, which **will be misinterpreted** by Compose. Verify what password a running container actually has:

```bash
docker exec -it hris-python-db-1 env | grep POSTGRES_PASSWORD
```

(Replace `hris-python-db-1` with your actual db container name if different — verify with `docker compose ps`.)

### 3. Single `.env` at the project root

There is only one `.env` file, at the project root — not inside `backend/`. Docker Compose reads it from the compose file's directory, and the local backend (via Pydantic Settings with `env_file="../.env"` relative to `backend/app/core/config.py`) reads the same file. Both must agree on shared values.

### 4. `compose.override.yml` must be in the same directory as `compose.yml`

Docker Compose only auto-merges files named `compose.*.yml` that sit next to `compose.yml`. If ports defined in the override aren't appearing in `docker compose config`, try forcing recreation:

```bash
docker compose up db -d --force-recreate
```

---

## Daily Startup Sequence

Run these in order:

1. **Start the database only:**
   ```bash
   docker compose up db -d
   ```

2. **Verify it's running and healthy:**
   ```bash
   docker compose ps
   ```
   Confirm `db` shows `healthy` in the state column and the port column shows `0.0.0.0:5433->5432/tcp` (or your configured host port).

3. **Start the backend via VS Code debugger:**
   - Open the **Run and Debug** panel in VS Code
   - Select **"FastAPI: Debug"**
   - Press `F5`
   - Confirm it's running at **http://localhost:8000/docs**

   The backend reads DB connection info from `.env` at startup; if you change `.env` you must restart the debugger session.

4. **Start the frontend:**
   ```bash
   cd frontendv3 && pnpm dev
   ```
   Confirm Vite is running at the printed localhost URL (commonly `http://localhost:5173`; if that port is busy it will auto-increment — check the terminal output for the actual URL).

---

## Shutdown Sequence

- **Stop frontend:** `Ctrl+C` in its terminal
- **Stop backend debugger:** `Shift+F5` in VS Code
- **Database:** can be left running, or stopped with `docker compose down`

---

## When to Use Full Docker Compose Instead

Only for integration testing before pushing — running the entire stack together (db + backend + frontend + Traefik) as it would run in production:

```bash
docker compose -f compose.yml -f compose.traefik.yml up -d --build
```

> **Caution:** `compose.yml` references `${DOCKER_IMAGE_BACKEND}` and `${TAG}` image variables that are not defined in `.env`. This full-stack command is intended for the CI/CD deployment pipeline, which injects them at runtime. Running it locally without those images built and tagged will fail. Do **not** use this for daily development.

This full-stack Docker workflow is **not** the daily development workflow described above.

---

## First-Time Setup (new machine or fresh clone)

1. Clone the repo
2. Copy `.env` with correct values (never commit real secrets — keep `.env` git-ignored)
3. Confirm `POSTGRES_PORT=5433` in `.env` matches the port mapping in `compose.override.yml`
4. Start the database: `docker compose up db -d`
5. Verify it's healthy: `docker compose ps`
6. If the `app` database doesn't exist yet:
   ```bash
   docker exec -it hris-python-db-1 psql -U postgres -c "CREATE DATABASE app;"
   ```
   (Verify the container name with `docker compose ps` — it may differ based on your project directory name.)
7. Run database migrations against the running DB:
   ```bash
   cd backend && uv run alembic upgrade head
   ```
8. Proceed with the Daily Startup Sequence above

---

## Project Scripts Summary

| Command | Location | Purpose |
|---------|----------|---------|
| `pnpm dev` | `frontendv3/` | Start Vite dev server |
| `uv run alembic upgrade head` | `backend/` | Apply pending DB migrations |
| `docker compose up db -d` | project root | Start Postgres container only |
| `docker compose ps` | project root | Check service status |
| `docker compose down` | project root | Stop all compose services |
