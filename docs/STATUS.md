# Status (hand-maintained snapshot)

Last updated: 2026-10-02. Baseline: the full E2E completion change, PR #70,
verified locally with scripts/verify.sh and a separate fresh-database browser run.
This file is hand-maintained; docs/MAP.md is generated. Refresh observed counts
after changes rather than preserving dated baseline claims.

## Verification

| Metric | Observed result | Evidence |
| --- | --- | --- |
| Backend tests | 707 passed, 0 failed | scripts/verify.sh, 2026-10-02 |
| Backend test files | 51 | Python pathlib rglob("test_*.py") under backend/tests |
| mypy app | 0 errors, 98 source files | scripts/verify.sh |
| Ruff | clean | scripts/verify.sh |
| Alembic migrations | 23, single head 3f0e3e733925; no drift | migration inventory and scripts/verify.sh |
| API endpoints / route groups | 226 / 39 | generated docs/MAP.md |
| Domain packages | 12 | generated docs/MAP.md |
| Vitest | 88 files / 280 tests passed | scripts/verify.sh |
| Feature test files | 77 | pathlib inventory excluding screenshot artifacts |
| Playwright | 40 passed, 25 specs, no retries | fresh disposable DB browser run |
| TypeScript | 0 errors | scripts/verify.sh |
| ESLint | 0 errors / 2 warnings, report-only | scripts/verify.sh |
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

Deployments require a PR merge, build immutable SHA-tagged images, take a
backup, migrate, wait for container health, and run nine HTTP checks. Audit
retention defaults to 90 days with deletion disabled until explicitly enabled.
See docs/runbooks/ for deployment, recovery, and retention procedures.

No coverage percentage gate is configured. mypy is a hard gate; ESLint remains
report-only. CodeQL alert counts and worktree lists are live external state:
query them when needed rather than treating an old snapshot as current.

## Coverage limits

Employee UI supports list/profile and CSV import, not a full manual CRUD form.
Leave ledger selection is incomplete; the E2E check covers its shell only.
Template apps/chats/tasks/users/settings are mock-backed demos. Existing
production data is not a CI fixture. Operational documentation now covers
architecture, decisions, modules, plans, testing, and archive provenance.

Historical migration downgrade anomalies remain deliberately preserved.
See docs/runbooks/migration-limitations.md and the owner's recorded decision.
Historical Symfony security work is excluded at the owner's request.
