# Testing and verification

Run bash scripts/verify.sh from the repository root for every change. It uses a disposable PostgreSQL container and placeholder credentials, checks ruff, mypy, migration drift, the complete backend suite, TypeScript, ESLint, Vitest browser tests, MAP drift and the frontend build. Ruff, mypy, drift, pytest, TypeScript, Vitest and build are hard gates. ESLint and MAP drift report results; warning counts are recorded in STATUS rather than assumed.

Backend tests live under backend/tests by domain. Cover unauthenticated rejection, missing permissions, ownership, validation, business transitions and persistence. All registered GET routes receive behavioral authentication checks as well as the existing static dependency-policy checks.

Frontend tests are colocated *.test.tsx files using Vitest's real browser mode. Assert exact request payloads, associations and backend field/value types. Keep full-suite counts in [STATUS](../STATUS.md).

Playwright specs live under frontendv3/e2e. CI creates a fresh PostgreSQL service, migrates and seeds placeholder users, then runs every spec against local API/frontend servers. The E2E seed requires explicit opt-in and a loopback database. Browser fixtures use placeholder credentials configured through E2E variables. The isolated job raises its login-attempt quota because independent browser sessions share a server bucket; production defaults are unaffected and backend rate-limit tests remain enabled.

Run pnpm exec playwright test from frontendv3 with a disposable database and the CI environment configuration. Authentication specs cover login, logout, refresh and permission denial. CRUD journeys create their own parent records, assert final HTTP results after redirects, read persisted data and delete their own rows. Never conditionally pass edit/delete checks because no row exists.

See [detailed frontend strategy](../../frontendv3/docs/testing-strategy.md) and [development workflow](../feature-development-workflow.md). Never use production data or credentials in tests or reports.

## Repeatable local browser QA

After installing dependencies and Chromium (`uv sync` in backend, `pnpm install --frozen-lockfile` and `pnpm exec playwright install chromium` in frontendv3), run from the repository root:

```bash
bash scripts/run-e2e-qa.sh                          # complete browser suite
bash scripts/run-e2e-qa.sh hris/batch1-workflows.spec.ts  # employee/salary/leave setup
bash scripts/run-e2e-qa.sh payroll                   # payroll/configuration
bash scripts/run-e2e-qa.sh attendance                # attendance/leave
bash scripts/run-e2e-qa.sh system/roles.spec.ts       # custom role lifecycle
bash scripts/run-e2e-qa.sh projects hris/emp-tasks.spec.ts # relationships/projects/tasks
```

On hosts missing browser shared libraries, run `bash frontendv3/scripts/setup-playwright-libs.sh` once. Docker, uv, pnpm, Python 3, curl, setsid and flock must be available. On WSL, the runner also supports Docker Desktop's standard Windows CLI path when its Linux CLI link is unavailable. The daemon must already be running.

The runner reuses `hris-ui-qa-e2e` (postgres:18, user/database e2e, loopback port 55603), or creates it if missing. It creates a unique database, migrates/seeds placeholder accounts, owns ports 8000/5173 and runs Chromium serially without retries. It drops only its own database and restores the QA container's original running/stopped state. Server logs are retained under the printed `/tmp/hris-ui-qa-*` path. Do not run two QA stacks concurrently or override the URLs with production addresses.

For production, use the separate **read-only** smoke entry point `python3 scripts/verify-deployment.py` (nine HTTP checks); never run CRUD browser specs against production. Hosted CI also exercises the full browser suite on each PR and after merge.
