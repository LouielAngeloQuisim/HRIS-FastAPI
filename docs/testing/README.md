# Testing and verification

Run bash scripts/verify.sh from the repository root for every change. It uses a disposable PostgreSQL container and placeholder credentials, checks ruff, mypy, migration drift, the complete backend suite, TypeScript, ESLint, Vitest browser tests, MAP drift and the frontend build. Ruff, mypy, drift, pytest, TypeScript, Vitest and build are hard gates. ESLint and MAP drift report results; two existing ESLint warnings are not zero warnings.

Backend tests live under backend/tests by domain. Cover unauthenticated rejection, missing permissions, ownership, validation, business transitions and persistence. All registered GET routes receive behavioral authentication checks as well as the existing static dependency-policy checks.

Frontend tests are colocated *.test.tsx files using Vitest's real browser mode. Assert exact request payloads, associations and backend field/value types. Keep full-suite counts in [STATUS](../STATUS.md).

Playwright specs live under frontendv3/e2e. CI creates a fresh PostgreSQL service, migrates and seeds placeholder users, then runs every spec against local API/frontend servers. The E2E seed requires explicit opt-in and a loopback database. Browser fixtures use placeholder credentials configured through E2E variables. The isolated job raises its login-attempt quota because independent browser sessions share a server bucket; production defaults are unaffected and backend rate-limit tests remain enabled.

Run pnpm exec playwright test from frontendv3 with a disposable database and the CI environment configuration. Authentication specs cover login, logout, refresh and permission denial. CRUD journeys create their own parent records, assert final HTTP results after redirects, read persisted data and delete their own rows. Never conditionally pass edit/delete checks because no row exists.

See [detailed frontend strategy](../../frontendv3/docs/testing-strategy.md) and [development workflow](../feature-development-workflow.md). Never use production data or credentials in tests or reports.
