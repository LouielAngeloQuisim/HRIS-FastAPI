# AGENTS.md

## 1. Project Overview

This repository is an HRIS (Human Resource Information System) project, rewritten from the original FastAPI full-stack template scaffold. The rewrite is driven by a written design/analysis doc set in `docs/roadmap/` and `analysis/` — **treat those as the source of truth for design decisions** (data model, payroll, attendance, leave, auth/RBAC, frontend design, rewrite plan). Key documents: `docs/roadmap/frontend-phase2-3-design.md` and `analysis/01-backend-datamodel.md` … `analysis/08-rewrite-plan.md`.

The original template shell (FastAPI + SQLModel + Alembic, generic user/item CRUD, admin-table frontend) is still present, but the HRIS rewrite is well underway: a domain backend module, a full frontend feature set, a custom JWT auth system with RBAC, and a phase-0-3 test suite. Some template features remain as unwired demos (see Known Gaps).

### Documentation map (source of truth)

- `docs/ROADMAP.md` — **the authoritative numbered cleanup roadmap** (tasks #1–#94). Task numbers are stable identifiers; never renumber or replace them with the phase JSON trackers.
- `docs/MAP.md` — generated repository architecture map (routes, permissions, domains, features, migration chain); regenerate with `bash scripts/gen-map.sh`, do not hand-edit; `scripts/verify.sh` drift-checks it.
- `docs/STATUS.md` — hand-maintained current status/counts snapshot (see that file's header for its maintenance model).
- `docs/README.md` — documentation index. `docs/runbooks/` — authoritative operational procedures (§8 below is a summary only).
- `docs/feature-development-workflow.md` — end-to-end process for any change: worktree from `origin/main`, one plan per task, implementation, `scripts/verify.sh`, PR with evidence. The `.kilo/` directory is intentionally untracked (see `.gitignore`); this document is the tracked source of the workflow.

## 1.5 Mandatory Testing Policy

Before changing tests, fixtures or runners, read [`docs/testing/test-policy.md`](docs/testing/test-policy.md). It is the detailed source of truth for risk-based coverage, runner selection, validation cadence, isolation, diagnosis and evidence. Operational commands are in [`docs/testing/README.md`](docs/testing/README.md).

During development, run targeted checks. For a finished batch, run `bash scripts/verify.sh` and relevant E2E coverage; repeat when later changes or failures justify it. Add meaningful regression coverage for executable changes and choose the lowest layer that proves the behavior, with E2E for critical integrated workflows. Do not use fixed test-file lists, counts or coverage targets as quality goals. Report actual results, skips, failures and coverage limits; never claim a pass without observed output. For documentation-only changes, state why no functional test applies and run documentation/link checks and the repository gate.

## 2. Current Status

### Backend - 797 tests green (verified 2026-10-05 by scripts/verify.sh)
- **Backend inventory:** 57 test files under backend/tests; the domain groups below describe responsibilities, not the current total by phase.
- **Phase 2A/2B — Attendance module** (`backend/app/attendance/`): full CRUD for `Shift` + `DailyTimeRecord`, plus `DTRAdjustment`. Routers under `/shifts`, `/daily-time-records`, `/dtr-adjustments`. Row-level filter on DTR list: non-superusers see only their own records; users with no linked EmployeeRecords see `[]`.
- **Phase B3 — Leave & Holidays module** (`backend/app/leave/`): full CRUD for `LeavePolicy`, `EmployeeLeaveEnrollment`, `LeaveRequest`, `LeaveLedgerEntry`, `HolidayConfig`, `HolidayInstance`. 84 tests in `backend/tests/leave/`.
- **Additional backend modules on `origin/main`** (phase trackers lag the code — treat the modules, not `docs/roadmap/*.json`, as truth): `payroll` (routers under `/payroll/*` incl. `runs/generate` gated by `payroll:add`), `notification`, `audit`, `reports`, `dashboard`. Full generated inventory: `docs/MAP.md` (250 endpoints in 39 groups across 12 domain packages).
- **25 Alembic migrations** (`backend/alembic/versions/`, verified 2026-10-05 via `ls backend/alembic/versions/*.py | wc -l`).
- All 16 HRIS domain resource routers are implemented in the `employee` module and served via the `routers` list in `app/employee/routes.py`: **employees, divisions, departments, subdivisions, positions, project-types, projects, phases, blocks, lots, categories, models, model-types, owners, employee-projects, emp-tasks** — plus `/dashboard`, `/rbac`, `/items`, `/users`, `/auth`, `/shifts`, `/daily-time-records`, `/dtr-adjustments`, `/leave/*`, notifications, audit, reports, payroll, and local-only `/private`.

### Frontend - 121 test files / 431 tests green (verified 2026-10-05)
- Full Vitest run: **121 test files / 431 tests passing** (2026-10-05).
- CRUD-complete feature pages with tests: divisions, departments, subdivisions (create wizard with failure-resume), positions, project-types, projects, phases, blocks, lots, categories, models, model-types, owners, employee-projects, emp-tasks, shifts, roles (admin + permission matrix + protected custom deactivation), dashboard, employees (**core CRUD + profile + CSV import**), salary setup, leave workflows and statutory payroll configuration.
- §8.1–§8.13 coverage: permission gating, 409 delete-error flows, CSV import success/retry, subdivision wizard state + resume.
- **Playwright E2E infrastructure:** `e2e/fixtures/`, `e2e/helpers/`, `e2e/pages/`, 26 page objects and 34 specs across organization, projects, HRIS, system, attendance, payroll and auth. Verified 2026-10-05: 66 passing journeys without retries, with stable `data-testid` selectors. Run all or per-module with `bash scripts/run-e2e-qa.sh`; see docs/testing/README.md.

## 3. Known Gaps

- **7 inert local `resource-delete-dialog` copies** (chats, dashboard, employees, roles, settings, tasks, users) carry the ErrorBody fix but are not imported anywhere (verified 2026-09-24: `git ls-files "*resource-delete-dialog.tsx"` lists 26 files, of which 25 are feature-local plus 1 shared, and `grep -rln` shows those 7 features' copies have zero importers; the `shared/` copy is imported by 23 files).
- **EmployeeAttachments UI gap:** backend model + tests exist; the frontend annex/attachments UI is deferred.
- **Unwired template demo features:** `apps`, `chats`, `tasks`, `users`, `settings` are complete shadcn-admin template UIs backed by local `./data/` mocks — no HRIS backend wiring.
- Minor: ~~`react-refresh/only-export-components` warning from exporting `extractDeleteErrorMessage` from the shared delete-dialog component module~~ resolved by PR #42 (helper extracted into its own module; no react-refresh warning appears in `npx eslint .` output as of 2026-09-28).
- Minor: ~~`frontendv3/src/lib/api/roles.ts:3` — `RolePublic` imported but never used~~ verified fixed (2026-09-24): `grep -n RolePublic frontendv3/src/lib/api/roles.ts` returns nothing.

## 4. Tech Stack

### Backend (`backend/pyproject.toml`)
- Python >=3.14,<4.0; production image and CI use Python 3.14. Local verification uses the interpreter available on the host; production-image builds were separately verified.
- `fastapi[standard] >=0.114.2,<1`, `pydantic >2.0`, `pydantic-settings >=2.2.1`, `sqlmodel >=0.0.21`, `alembic >=1.12.1`, `psycopg[binary] >=3.1.13`, `pyjwt >=2.8.0`, `pwdlib[argon2,bcrypt] >=0.3.0`, `tenacity >=8.2.3`, `httpx >=0.25.1`, `emails >=0.6`, `jinja2 >=3.1.4`, `email-validator`, `sentry-sdk[fastapi] >=2.20.0`, `python-multipart >=0.0.7`.
- Dev: pytest `>=7.4.3,<8`, mypy (strict), ruff, prek, coverage. **No coverage gate exists** (verified 2026-09-24: `grep -rn "fail-under\|coverage report" .github/workflows/` returns nothing and `backend/pyproject.toml` has no `fail_under`), contrary to the old claim of a CI-enforced 90%.

### Frontend (`frontendv3/package.json`, caret ranges)
- Build runtime: Node 26; pnpm 11.17.0 installed explicitly because Node 26 does not bundle Corepack.
- react `^19.2.5` / react-dom `^19.2.5`, typescript `~6.0.3`, vite `^8.0.8` (+ `@vitejs/plugin-react`), @tanstack/react-router `^1.168.22` (file-based), @tanstack/react-query `^5.99.0`, @tanstack/react-table `^8.21.3`, tailwindcss `^4.2.2` + `@tailwindcss/vite`, lucide-react `^1.8.0`, zod `^4.3.6`, react-hook-form `^7.72.1` + `@hookform/resolvers`, sonner `^2.0.7`, **axios `^1.15.0`**, zustand `^5.0.12`, recharts `^3.8.1`, date-fns, class-variance-authority, tailwind-merge, clsx, cmdk, input-otp, react-day-picker, react-top-loading-bar, tw-animate-css, Radix UI primitives (alert-dialog, avatar, checkbox, collapsible, dialog, direction, dropdown-menu, icons, label, popover, radio-group, scroll-area, select, separator, slot, switch, tabs, tooltip).
- Dev: eslint `^10.2.1` + typescript-eslint + eslint-plugin-react-hooks + eslint-plugin-react-refresh, prettier `^3.8.3` (+ @trivago/prettier-plugin-sort-imports, prettier-plugin-tailwindcss), vitest `^4.1.4` (browser-playwright, coverage-v8, ui), playwright `1.62.1`, @faker-js/faker, @testing-library/react, knip, happy-dom, @tanstack/router-plugin + devtools.
- **Auth:** custom JWT (see §5).
- **Explicit corrections vs the old template AGENTS.md:** there is **no Biome** (lint is eslint, format is prettier), **no next-themes** (theme is a custom `ThemeProvider`), **no @hey-api/openapi-ts client** (hand-written axios client), and **`frontendv3/`** is the frontend (the tracked template `frontend/` folder was removed in PR #26; a root `frontend/` directory still exists on some dev hosts as an untracked residue of empty `blob-report/` + `test-results/` dirs — tracked file count 0; removal is roadmap #90).

### Infrastructure / CI-CD
- PostgreSQL `18` (`postgres:18`), Traefik `3.7` (`compose.traefik.yml`), Nginx for frontend static serving (prod), GitHub Container Registry (GHCR) + GitHub Actions deployment. Compose split: `compose.yml` (base), `compose.override.yml` (dev), `compose.prod.yml` (prod), `compose.traefik.yml`.

## 5. Architecture Conventions

### Backend
- **Domain packages, not one-file-per-resource.** Each domain is a package (e.g. `app/employee/`, `app/auth/`, `app/rbac/`, `app/user/`) layering `models.py` / `schemas.py` / `routes.py` / `services.py` / `selectors.py`. `app/employee/routes.py` uses a router factory (`_make_crud_router`) to build **16 per-resource routers** (`/employees`, `/divisions`, `/departments`, `/subdivisions`, `/positions`, `/project-types`, `/projects`, `/phases`, `/blocks`, `/lots`, `/categories`, `/models`, `/model-types`, `/owners`, `/employee-projects`, `/emp-tasks`), aggregated in a module-level `routers: list[APIRouter]` at `backend/app/employee/routes.py:594` (verified 2026-09-28: `grep -c "_router = " backend/app/employee/routes.py` = 16; the file contains no `include_router`/`sub_router` tokens; `app/api.py:22` loops `for employee_router in employee_routes.routers`). `app/api.py` includes auth, users, items, utils, rbac, employee (16 routers), attendance, leave, notifications, audit, payroll, reports, dashboard, and local-only private.
- **Shared infra in `app/common/`:** `responses.py` (ErrorBody `{success, error, request_id}` envelope), `pagination.py`/`paginators.py`, `rate_limit.py` + deps, `route_policy.py` (public-route whitelist incl. `POST /api/v1/login/refresh-token`), `security.py`, `regex.py`, `schemas.py`, `types.py`, `audit/`.
- **Auth:** custom JWT. Access token + **rotating single-use refresh token** (PyJWT). `POST /api/v1/login/refresh-token` rotates the refresh token; `route_policy` marks it public. Passwords via pwdlib (Argon2 primary, Bcrypt fallback). RBAC enforced via route policy / `require_permission`.
- **DB:** SQLModel tables, Alembic migrations in `backend/alembic/versions/` (25, same count as §2, verified 2026-10-05), engine/config in `app/config/`.

### Frontend
- **Feature-dir pattern:** each domain is `src/features/<domain>/index.tsx` (page) + `components/` + feature-scoped tests beside source. Data access via hooks in `src/lib/api/<domain>.ts` (`useQuery`/`useMutation` + `invalidateQueries` on the shared axios `api` client). Server state via TanStack Query; client state via zustand (`src/stores/auth-store.ts`).
- **RBAC:** `useCan(module, action)` from `src/context/permissions-provider.tsx`, with **exact action literals `'view' | 'add' | 'edit' | 'delete'`** (never `'create'`/`'update'`). Row-level Edit/Delete buttons are gated with `canEdit`/`canDelete` (17 list features, verified 2026-09-24 by `index.tsx` scan) or `canUpdate` (roles). `usePermissions` throws if the provider value is `undefined` — the context value must be `null`-normalized while the permissions query is loading.
- **Auth flow:** tokens in cookies `hris_at`/`hris_rt` (7-day max-age); axios request interceptor attaches `Bearer <access>`; response interceptor performs a **single-use refresh on 401** through a raw (interceptor-free) instance (`refreshInFlight` dedupe, `_retry` guard against loops), clearing tokens on refresh failure.
- **Delete-confirm toasts:** shared `extractDeleteErrorMessage` reads `err.response.data.error.message` → `.detail` → generic fallback; used in the shared dialog plus the 25 feature-local copies (verified 2026-09-24: `git ls-files | grep -c resource-delete-dialog.tsx` = 26 = 1 under `src/components/` + 25 under `src/features/`).

## 6. Frontend Test Environment

- **Vitest browser mode** (`vitest run --browser.headless`, Playwright-backed). On this host, run once: `frontendv3/scripts/setup-playwright-libs.sh`, then export `LD_LIBRARY_PATH="$(pwd)/.playwright-libs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"` before running tests.
- Commands (from `frontendv3/`): full suite `npx vitest run --browser.headless`; single file `npx vitest run --browser.headless <path>`; lint `npx eslint .`; format `npx prettier --write .`; typecheck `npx tsc --noEmit`.
- Test conventions: `renderWithClient` from `@/test-utils/providers`, `userEvent` from `vitest/browser`, hoisted `vi.mock` blocks (per-action `useCan` policy mock, `use*` hook mocks, axios `api.delete` mocks, sonner toast spies).
- Baseline (verified 2026-10-05): **797 backend tests, 121 frontend files / 431 Vitest tests, 25 migrations with no drift, tsc 0 errors, mypy 0 errors (98 source files), ruff clean, ESLint 0 errors / 7 warnings**. ESLint warnings remain report-only.
- Playwright E2E: **66 passing browser tests across 34 specs**, verified on a disposable database without retries. The dedicated e2e workflow runs on PRs and main. See docs/plans/e2e-ci-completion.md for isolation guards and coverage limits. Never point the CI suite at production.


## 7. Lessons Learned (verified, no current regressions)

- **useCan action-literal discipline:** 0 occurrences of `'create'`/`'update'` anywhere in `src/` today — only `'view' | 'add' | 'edit' | 'delete'`.
- **Row-level permission gating** is applied across all list pages (verified 2026-09-24: 17 features with `canEdit`+`canDelete` in `index.tsx`, roles with `canUpdate`).
- **ErrorBody-specific 409 messages** are surfaced in delete toasts (asserted by §8.7/§8.8 tests asserting exact message text, not just "a toast appeared").
- **DTR row-level filter `None` trap:** When a non-superuser has no linked EmployeeRecords, passing `employee_id_filter=None` to the selector skips the filter entirely (since the selector guards `if employee_id_filter is not None`). The correct pattern is an early return `return []` when the linked employee is `None` — do not rely on the selector to handle this case.
- **Infra:** a `$` in `.env` values is escaped only for Docker Compose (`$$`) — pydantic-settings/pytest read the file literally, so the durable fix is a `$`-free password. `POSTGRES_PORT` differs between host (5433) and container (5432): keep `POSTGRES_PORT=5432` inside compose prestart/backend services or prestart will retry for ~5 minutes then fail.

## 8. Production Deploy & VM Access (summary only)

The authoritative step-by-step procedures are the runbooks in `docs/runbooks/`: `docs/runbooks/deploy.md`, `docs/runbooks/rollback.md`, `docs/runbooks/migrations.md`, `docs/runbooks/backup-restore.md`. This section 8 is only a summary — follow the runbooks for any production operation.

- Deploys happen **ONLY by merging a pull request to `main`** (never by direct push; `main` is protected by the `Main Branch Rules` ruleset: PR required, no deletion, no force-push, `backend`/`frontend`/`e2e` status checks required).
- The deploy pipeline (see `.github/workflows/deploy.yml`) runs: `ci` → `build-and-push` → `deploy` (pre-deploy `pg_dump`, migrate via `scripts/prestart.sh` (`alembic upgrade head`), `docker compose -f compose.prod.yml up -d`, health-check wait until backend, frontend, and Traefik report healthy) → `verify` (nine HTTP checks covering health, authentication, disabled documentation, HTML pages, and HTTPS redirects).
- `hris-deploy deploy` (the restricted VM SSH command) only runs `compose pull` + `compose up -d`. It skips the dump, the migration, and the health-check wait. It must **NEVER** be used when a migration is pending, and is **not** a substitute for a PR merge. It is only safe for restarting already-running, already-migrated containers.
- `hris-debug` remains read-only (`ps`, `logs`, `inspect`, `stats`, `df`, `free`) for checking status.

### Evidence requirement

Any agent report claiming a push, commit, PR creation, deploy, or test result succeeded must be backed by an actual command whose raw output is shown (e.g. `git ls-remote`, `gh pr list`, `gh pr checks`). A summary alone is not sufficient evidence.

## 9. Secrets / Environment / AI-prompt Safety (policy)

Documentation-only policy — there is no secret-scanning hook or CI gate enforcing these rules yet (roadmap #40 tracks the pending history scan; roadmap #92's `ci-config-check` job — merged in PR #57 — validates workflow configuration only, not content). Treat them as project rules, not as claims of technical enforcement.

- **Secrets never enter the repository.** Real `.env` values, tokens, DB passwords, and production credentials belong in the git-ignored `.env` (root) and in GitHub Actions secrets — never in a tracked file, a commit message, a PR body, or an issue. The only committed env material is placeholder-grade (`backend/env_sample.txt`, `frontendv3/.env.example`).
- **Never paste real environment values into terminal output, tests, docs, or reports.** Echo key names / redact values. This applies to agent output as well as humans.
- **Do not put production credentials or production data into AI prompts**, logs, screenshots, or test fixtures. Use throwaway values (as `scripts/verify.sh` does) for any reproduction.
- **Logs must not record secrets.** The audit middleware redacts bodies (`AUDIT_BODY_MAX_BYTES`); keep it that way when extending logging.
- **AI/agent coding sessions** must follow the same evidence rules as §1.5/§8: read-only inspection first, no direct edits on `main`, no history rewrites, and any discovered secret is reported as a finding (via the process in `SECURITY.md`), not "cleaned up" silently.
- **Historical template artifact:** `.copier/.copier-answers.yml` is still tracked and contains template-era credential-shaped placeholder values; its disposition is deliberately held under roadmap #40/#88 — do not delete or rewrite it (or any git history) without the owner's security decision.
