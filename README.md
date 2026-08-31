# HRIS — Human Resource Information System

A full-stack HRIS application built with FastAPI + React, covering core HR workflows: employee records, attendance, payroll, leave management, and organizational structure.

## Technology Stack

### Backend (`backend/`)
- [**FastAPI**](https://fastapi.tiangolo.com) — Python web API
- [**SQLModel**](https://sqlmodel.tiangolo.com) — ORM (SQLAlchemy + Pydantic)
- [**Alembic**](https://alembic.sqlalchemy.org) — database migrations
- **PostgreSQL 18** — database
- **Custom JWT auth** — access + rotating refresh tokens, Argon2 password hashing
- **RBAC** — permission-based access control with role/seat assignment
- **pytest** — 275 tests (backend)

### Frontend (`frontendv3/`)
- [**React 19**](https://react.dev) + [**TypeScript**](https://www.typescriptlang.org)
- [**Vite**](https://vite.dev) — build tool
- [**TanStack Router**](https://tanstack.com/router) — file-based routing
- [**TanStack Query**](https://tanstack.com/query) — server state
- [**Tailwind CSS v4**](https://tailwindcss.com) + [**shadcn/ui**](https://ui.shadcn.com) — UI components
- [**Zustand**](https://zustand-demo.pmnd.rs) — client state
- **Axios** — HTTP client
- **Vitest + Playwright** — 187 browser-mode tests

### Infrastructure
- **Docker Compose** — development + production
- **Traefik 3** — reverse proxy / load balancer
- **GitHub Actions** — CI/CD with automatic deploy to staging

## Features

### Completed Modules

| Module | Status |
|--------|--------|
| **Employees** | Read-only list + profile + CSV import (backend: full CRUD) |
| **Divisions / Departments / Subdivisions** | Full CRUD with create wizard |
| **Positions / Project Types / Projects / Phases** | Full CRUD |
| **Blocks / Lots / Categories / Models / Model Types** | Full CRUD |
| **Owners** | Full CRUD |
| **Employee Projects / Emp Tasks** | Full CRUD |
| **Shifts** | Full CRUD (backend + frontend) |
| **Daily Time Records (DTR)** | Full CRUD with row-level security; HR sees all, employees see own |
| **DTR Adjustments** | HR-approved attendance corrections |
| **Roles + Permissions** | Admin UI with permission matrix |
| **Dashboard** | KPI cards |
| **Auth** | Login, JWT tokens, RBAC-gated sidebar |

### Deferred (per design §7)
- Employee create/edit/delete UI (backend exists, frontend read-only)
- Employee attachments/annex UI
- Leave management module
- Payroll module

## Project Phases

See [`docs/roadmap/frontend-phase2-3-design.md`](./docs/roadmap/frontend-phase2-3-design.md) for the full phase plan and [`AGENTS.md`](./AGENTS.md) for current status.

Current: **Phase 2A/2B (backend) + Phase 3 (frontend) complete.**

## Local Setup

### Prerequisites
- Python 3.12+ (with `uv`)
- Node.js 20+ (with `pnpm`)
- Docker 28+ (with `docker compose`)

### 1. Clone and configure

```bash
git clone https://github.com/LouielAngeloQuisim/HRIS-FastAPI.git
cd HRIS-FastAPI
cp .env.example .env  # edit as needed
```

### 2. Start infrastructure

```bash
docker compose up -d postgres traefik
```

### 3. Backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python -m pytest tests/ -q          # 275 tests
uv run uvicorn app.main:app --reload       # http://localhost:8000
```

### 4. Frontend

```bash
cd frontendv3
pnpm install
pnpm run dev                               # http://localhost:5173
```

To run frontend tests (first-time setup required):

```bash
cd frontendv3
bash scripts/setup-playwright-libs.sh       # one-time: download Chromium libs
LD_LIBRARY_PATH="$(pwd)/.playwright-libs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH" \
  pnpm test                                # 187 tests
```

## Environment Variables

Key variables in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key | `changethis` (change!) |
| `POSTGRES_PASSWORD` | Database password | `changethis` (change!) |
| `FIRST_SUPERUSER_PASSWORD` | Initial admin password | `changethis` |
| `POSTGRES_HOST` | DB host | `localhost` |
| `POSTGRES_PORT` | DB port | `5432` (container) / `5433` (host debugger) |

> **Note:** Do not use a `$` character in `POSTGRES_PASSWORD` — Docker Compose and pydantic-settings interpret `$$` differently and there is no compatible escaping scheme. Use a `$`-free password.

## Database Migrations

Migrations live in `backend/alembic/versions/`. After pulling changes:

```bash
cd backend
uv run alembic upgrade head
```

## API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Deployment

Staging deploy is automatic on push to `main` via GitHub Actions (`deploy.yml`).

See [`deployment.md`](./deployment.md) for production deployment instructions.

## License

MIT
