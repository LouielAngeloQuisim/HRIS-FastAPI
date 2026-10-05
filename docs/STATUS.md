# Status (hand-maintained snapshot)

Last updated: 2026-10-05. Baseline: the combined employee/leave/payroll/administration QA finish pass,
verified locally with scripts/verify.sh and a separate disposable-database browser run.
This file is hand-maintained; docs/MAP.md is generated. Refresh observed counts
after changes rather than preserving dated baseline claims.

## Verification

| Metric | Observed result | Evidence |
| --- | --- | --- |
| Backend tests | 807 passed, 0 failed, 0 skipped | scripts/verify.sh, 2026-10-05 |
| Backend test files | 58 | Python pathlib rglob("test_*.py") under backend/tests |
| mypy app | 0 errors, 98 source files | scripts/verify.sh |
| Ruff | clean | scripts/verify.sh |
| Alembic migrations | 25, single head 8c12ab55d901; no drift | migration inventory and scripts/verify.sh |
| API endpoints / route groups | 250 / 39 | generated docs/MAP.md |
| Domain packages | 12 | generated docs/MAP.md |
| Vitest | 121 files / 431 tests passed | scripts/verify.sh |
| Feature test files | 105 | pathlib inventory excluding screenshot artifacts |
| Playwright | 66 passed, 34 specs, 0 retries; 392.85 s at 1 worker | isolated local QA DB, 2026-10-05 |
| TypeScript | 0 errors | scripts/verify.sh |
| ESLint | 0 errors / 7 warnings, report-only | scripts/verify.sh |
| Frontend build | passed | scripts/verify.sh |
| Architecture map | in sync | scripts/verify.sh |
| Overall gate | RESULT: PASS (exit 0) | scripts/verify.sh |

Verification uses placeholder credentials and disposable PostgreSQL.
Do not read production .env files to collect tests or run CI against production.
The browser suite is a separate dedicated CI job, not part of verify.sh.

## Runtime and operations

Production images and CI use Python 3.14, Node 26, and Traefik 3.7.
Node 26 requires explicit pnpm installation. Reviewed Dependabot proposals
and image-build evidence are recorded in docs/plans/runtime-upgrades-2026-10-02.md.
Workflows: ci.yml, deploy.yml, e2e.yml. CI runners use ubuntu-26.04.

Main protection requires backend, frontend, and e2e checks.
Deployments require a PR merge, build immutable SHA-tagged images, take a
backup, migrate, wait for container health, and run nine HTTP checks. Audit
retention defaults to 90 days with deletion disabled until explicitly enabled.
See docs/runbooks/ for deployment, recovery, and retention procedures.

No coverage percentage gate is configured. mypy is a hard gate; ESLint remains
report-only. CodeQL alert counts and worktree lists are live external state:
query them when needed rather than treating an old snapshot as current.

## Coverage limits

Employee core create/edit/soft-archive, profile and CSV import are covered. Salary setup/recovery, leave policy/enrollment and request lifecycle with calendar/ledger readback have browser regressions. Employee attachment/201-file annex UI remains deferred. Statutory configuration lifecycle, transient payroll preview, identity-stable generation retry, role protection and readable relationships are covered.
Template apps/chats/tasks/users/settings are mock-backed demos. Existing
production data is not a CI fixture. Operational documentation now covers
architecture, decisions, modules, plans, testing, and archive provenance.

Historical migration downgrade anomalies remain deliberately preserved.
See docs/runbooks/migration-limitations.md and the owner's recorded decision.
Historical Symfony security work is excluded at the owner's request.
