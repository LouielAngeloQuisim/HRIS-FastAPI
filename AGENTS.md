# AGENTS.md

## 1. Project Overview

This repository is an HRIS (Human Resource Information System) project, rewritten from the original FastAPI full-stack template scaffold. The rewrite is driven by a written design/analysis doc set in `docs/roadmap/` and `analysis/` — **treat those as the source of truth for design decisions** (data model, payroll, attendance, leave, auth/RBAC, frontend design, rewrite plan). Key documents: `docs/roadmap/frontend-phase2-3-design.md` and `analysis/01-backend-datamodel.md` … `analysis/08-rewrite-plan.md`.

The original template shell (FastAPI + SQLModel + Alembic, generic user/item CRUD, admin-table frontend) is still present, but the HRIS rewrite is well underway: a domain backend module, a full frontend feature set, a custom JWT auth system with RBAC, and a phase-0-3 test suite. Some template features remain as unwired demos (see Known Gaps).

## 1.5 Mandatory Testing Policy — applies to EVERY change, no exceptions

**Every code change — however small, however "quick," including one-line
fixes, config tweaks, or "just this small module" requests — must include
a test and a full verification run before being reported as complete.**
This is not limited to planned phase work; it applies to ad-hoc fixes,
follow-up tweaks, and anything touching existing tested code.

This is NOT automatic behavior by default — it must be actively followed
on every task, not only when explicitly reminded in a prompt. Treat this
section itself as that standing reminder.

### For any backend change (`backend/`):
1. Write or update a pytest test covering the change, in the matching
   `backend/tests/<domain>/` directory, following the existing patterns
   (see AGENTS.md §5 Architecture Conventions).
2. Run the FULL backend suite (`pytest tests/ -q` from `backend/`), not
   just the new/changed test file — confirm the total pass count and
   that it is not lower than the last known-good baseline (see §6 for
   current baseline numbers, kept up to date).
3. Run `ruff check` and `mypy` on changed files.
4. Only report the change as complete after all of the above pass, and
   state the actual pass count in the report (e.g. "248 passed, 0
   failed" — not "tests pass").

### For any frontend change (`frontendv3/`):
1. Write or update a Vitest browser-mode test covering the change,
   colocated with the source file per the existing convention (see §5
   Frontend Architecture Conventions, §6 Frontend Test Environment).
2. Run the FULL frontend suite (`npx vitest run --browser.headless`,
   with `LD_LIBRARY_PATH` set per §6), not just the new/changed test
   file — confirm the total pass count is not lower than the last
   known-good baseline.
3. Run `npx tsc --noEmit` and `npx eslint .` on changed files.
4. Only report the change as complete after all of the above pass, and
   state the actual pass count in the report.

### If a change touches BOTH backend and frontend:
Run both suites above — do not report complete after only one side is
verified.

### If writing a genuine test is not possible or not sensible for a given
change (e.g. a pure documentation edit, a config file with no testable
behavior):
State explicitly why no test applies — do not silently skip this section
without a stated reason. "No test needed: this is a documentation-only
change" is an acceptable statement; silence is not.

### Never claim "tests pass" or "implementation complete" without having
actually run the commands above in this session and observing real
output. A claim of completion without a stated, real pass count is not
acceptable — see Lessons Learned §7 for what happens when this discipline
is skipped (a "complete" phase report with 0 of 12 required tests
actually written, discovered only after being pushed back on multiple
times).

## 2. Current Status

### Backend — Phase 0-1 + Phase 2A/2B: 275 tests passing, 0 failed
- **Phase 0-1:** 21 test files in `backend/tests/`: `employee/` (crud, crud_relations, dashboard, owner/category/lots, blocks/lots delete-guard, attachments, additional_records, indexes_constraints), `auth/` (flow, rate-limit), `rbac/` (require_permission, route_protection, role_escalation, seed), `foundation/` (scaffold, responses), `item/`, `user/` (crud, private, routes), `scripts/` (pre-start waits).
- **Phase 2A/2B — Attendance module** (`backend/app/attendance/`): full CRUD for `Shift` + `DailyTimeRecord`, plus `DTRAdjustment`. Routers under `/shifts`, `/daily-time-records`, `/dtr-adjustments`. Row-level filter on DTR list: non-superusers see only their own records; users with no linked EmployeeRecords see `[]`.
- **12 Alembic migrations** (`backend/alembic/versions/`).
- All 17 HRIS domain resources are implemented in the `employee` module and served as sub-routers: **employees, divisions, departments, subdivisions, positions, project-types, projects, phases, blocks, lots, categories, models, model-types, owners, employee-projects, emp-tasks** — plus `/dashboard`, `/rbac`, `/items`, `/users`, `/auth`, `/shifts`, `/daily-time-records`, `/dtr-adjustments`, and local-only `/private`.

### Frontend — Phase 0-3: 187 tests, 43 files passing
- `vitest run --browser.headless` → **43 test files / 187 tests** green (57 test files exist on disk; the remainder are `__screenshots__` duplicates, excluded).
- CRUD-complete feature pages with tests: divisions, departments, subdivisions (create wizard with failure-resume), positions, project-types, projects, phases, blocks, lots, categories, models, model-types, owners, employee-projects, emp-tasks, shifts (**UI only**), roles (admin + permission matrix), dashboard, employees (**read-only list + profile + CSV import**).
- §8.1–§8.13 coverage: permission gating, 409 delete-error flows, CSV import success/retry, subdivision wizard state + resume.

## 3. Known Gaps

- **Employee create/edit/delete: NOT built in frontend** (deferred per design §7). Backend `/employees` CRUD exists; the frontend ships a read-only list, a profile view, and CSV import only.
- **6 inert local `resource-delete-dialog` copies** (chats, dashboard, employees, roles, settings, tasks, users) carry the ErrorBody fix but are not wired into any reachable delete flow.
- **EmployeeAttachments UI gap:** backend model + tests exist; the frontend annex/attachments UI is deferred.
- **Unwired template demo features:** `apps`, `chats`, `tasks`, `users`, `settings` are complete shadcn-admin template UIs backed by local `./data/` mocks — no HRIS backend wiring.
- Minor: `react-refresh/only-export-components` warning from exporting `extractDeleteErrorMessage` from the shared delete-dialog component module (fix: extract the helper to its own module).
- Minor: `frontendv3/src/lib/api/roles.ts:3` — `RolePublic` imported but never used (pre-existing lint error, non-blocking).

## 4. Tech Stack

### Backend (`backend/pyproject.toml`)
- Python `>=3.10,<4.0`; prod image `python:3.10` (`backend/Dockerfile`); **local venv is Python 3.12.3** (repo-root `.venv`).
- `fastapi[standard] >=0.114.2,<1`, `pydantic >2.0`, `pydantic-settings >=2.2.1`, `sqlmodel >=0.0.21`, `alembic >=1.12.1`, `psycopg[binary] >=3.1.13`, `pyjwt >=2.8.0`, `pwdlib[argon2,bcrypt] >=0.3.0`, `tenacity >=8.2.3`, `httpx >=0.25.1`, `emails >=0.6`, `jinja2 >=3.1.4`, `email-validator`, `sentry-sdk[fastapi] >=2.20.0`, `python-multipart >=0.0.7`.
- Dev: pytest `>=7.4.3,<8`, mypy (strict), ruff, prek, coverage. CI enforces `coverage report --fail-under=90`.

### Frontend (`frontendv3/package.json`, caret ranges)
- react `^19.2.5` / react-dom `^19.2.5`, typescript `~6.0.3`, vite `^8.0.8` (+ `@vitejs/plugin-react`), @tanstack/react-router `^1.168.22` (file-based), @tanstack/react-query `^5.99.0`, @tanstack/react-table `^8.21.3`, tailwindcss `^4.2.2` + `@tailwindcss/vite`, lucide-react `^1.8.0`, zod `^4.3.6`, react-hook-form `^7.72.1` + `@hookform/resolvers`, sonner `^2.0.7`, **axios `^1.15.0`**, zustand `^5.0.12`, recharts `^3.8.1`, date-fns, class-variance-authority, tailwind-merge, clsx, cmdk, input-otp, react-day-picker, react-top-loading-bar, tw-animate-css, Radix UI primitives (alert-dialog, avatar, checkbox, collapsible, dialog, direction, dropdown-menu, icons, label, popover, radio-group, scroll-area, select, separator, slot, switch, tabs, tooltip).
- Dev: eslint `^10.2.1` + typescript-eslint + eslint-plugin-react-hooks + eslint-plugin-react-refresh, prettier `^3.8.3` (+ @trivago/prettier-plugin-sort-imports, prettier-plugin-tailwindcss), vitest `^4.1.4` (browser-playwright, coverage-v8, ui), playwright `1.59.1`, @faker-js/faker, @testing-library/react, knip, happy-dom, @tanstack/router-plugin + devtools.
- **Auth:** custom JWT (see §5).
- **Explicit corrections vs the old template AGENTS.md:** there is **no Biome** (lint is eslint, format is prettier), **no next-themes** (theme is a custom `ThemeProvider`), **no @hey-api/openapi-ts client** (hand-written axios client), and the active frontend is **`frontendv3/`** (not `frontend/`).

### Infrastructure / CI-CD
- PostgreSQL `18` (`postgres:18`), Traefik `3.6` (`compose.traefik.yml`), Nginx for frontend static serving (prod), GitHub Container Registry (GHCR) + GitHub Actions deployment. Compose split: `compose.yml` (base), `compose.override.yml` (dev), `compose.prod.yml` (prod), `compose.traefik.yml`.

## 5. Architecture Conventions

### Backend
- **Domain packages, not one-file-per-resource.** Each domain is a package (e.g. `app/employee/`, `app/auth/`, `app/rbac/`, `app/user/`) layering `models.py` / `schemas.py` / `routes.py` / `services.py` / `selectors.py`. `app/employee/routes.py` uses a router factory to aggregate **17 per-resource sub-routers** (`/employees`, `/divisions`, `/departments`, `/subdivisions`, `/positions`, `/project-types`, `/projects`, `/phases`, `/blocks`, `/lots`, `/categories`, `/models`, `/model-types`, `/owners`, `/employee-projects`, `/emp-tasks`). `app/api.py` includes auth, users, items, utils, rbac, employee, dashboard, and local-only private.
- **Shared infra in `app/common/`:** `responses.py` (ErrorBody `{success, error, request_id}` envelope), `pagination.py`/`paginators.py`, `rate_limit.py` + deps, `route_policy.py` (public-route whitelist incl. `POST /api/v1/login/refresh-token`), `security.py`, `regex.py`, `schemas.py`, `types.py`, `audit/`.
- **Auth:** custom JWT. Access token + **rotating single-use refresh token** (PyJWT). `POST /api/v1/login/refresh-token` rotates the refresh token; `route_policy` marks it public. Passwords via pwdlib (Argon2 primary, Bcrypt fallback). RBAC enforced via route policy / `require_permission`.
- **DB:** SQLModel tables, Alembic migrations in `backend/alembic/versions/` (12), engine/config in `app/config/`.

### Frontend
- **Feature-dir pattern:** each domain is `src/features/<domain>/index.tsx` (page) + `components/` + feature-scoped tests beside source. Data access via hooks in `src/lib/api/<domain>.ts` (`useQuery`/`useMutation` + `invalidateQueries` on the shared axios `api` client). Server state via TanStack Query; client state via zustand (`src/stores/auth-store.ts`).
- **RBAC:** `useCan(module, action)` from `src/context/permissions-provider.tsx`, with **exact action literals `'view' | 'add' | 'edit' | 'delete'`** (never `'create'`/`'update'`). Row-level Edit/Delete buttons are gated with `canEdit`/`canDelete` (16 list features) or `canUpdate` (roles). `usePermissions` throws if the provider value is `undefined` — the context value must be `null`-normalized while the permissions query is loading.
- **Auth flow:** tokens in cookies `hris_at`/`hris_rt` (7-day max-age); axios request interceptor attaches `Bearer <access>`; response interceptor performs a **single-use refresh on 401** through a raw (interceptor-free) instance (`refreshInFlight` dedupe, `_retry` guard against loops), clearing tokens on refresh failure.
- **Delete-confirm toasts:** shared `extractDeleteErrorMessage` reads `err.response.data.error.message` → `.detail` → generic fallback; used by the shared + all 21 local `resource-delete-dialog.tsx` copies.

## 6. Frontend Test Environment

- **Vitest browser mode** (`vitest run --browser.headless`, Playwright-backed). On this host, run once: `scripts/setup-playwright-libs.sh`, then export `LD_LIBRARY_PATH="$(pwd)/.playwright-libs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"` before running tests.
- Commands (from `frontendv3/`): full suite `npx vitest run --browser.headless`; single file `npx vitest run --browser.headless <path>`; lint `npx eslint .`; format `npx prettier --write .`; typecheck `npx tsc --noEmit`.
- Test conventions: `renderWithClient` from `@/test-utils/providers`, `userEvent` from `vitest/browser`, hoisted `vi.mock` blocks (per-action `useCan` policy mock, `use*` hook mocks, axios `api.delete` mocks, sonner toast spies).
- Baseline: **187 frontend tests / 43 files, 275 backend tests, tsc 0 errors, eslint 0 errors** (a few pre-existing warnings).

## 7. Lessons Learned (verified, no current regressions)

- **useCan action-literal discipline:** 0 occurrences of `'create'`/`'update'` anywhere in `src/` today — only `'view' | 'add' | 'edit' | 'delete'`.
- **Row-level permission gating** is applied across all list pages (verified: 16 features with `canEdit`+`canDelete`, roles with `canUpdate`).
- **ErrorBody-specific 409 messages** are surfaced in delete toasts (asserted by §8.7/§8.8 tests asserting exact message text, not just "a toast appeared").
- **DTR row-level filter `None` trap:** When a non-superuser has no linked EmployeeRecords, passing `employee_id_filter=None` to the selector skips the filter entirely (since the selector guards `if employee_id_filter is not None`). The correct pattern is an early return `return []` when the linked employee is `None` — do not rely on the selector to handle this case.
- **Infra:** a `$` in `.env` values is escaped only for Docker Compose (`$$`) — pydantic-settings/pytest read the file literally, so the durable fix is a `$`-free password. `POSTGRES_PORT` differs between host (5433) and container (5432): keep `POSTGRES_PORT=5432` inside compose prestart/backend services or prestart will retry for ~5 minutes then fail.
