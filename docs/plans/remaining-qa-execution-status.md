# Remaining QA Execution Status

Updated 2026-10-05, Asia/Manila.

## Active batch

Batch 1: QA-05 employee CRUD, PAY-03 salary maintenance and missing-salary recovery, QA-04 leave workflows. Branch `fix/batch1-employee-leave-workflows`, PR [#75](https://github.com/LouielAngeloQuisim/HRIS-FastAPI/pull/75).

The implementation and regression fixes in the commit containing this checkpoint are locally validated. The previously pushed revision was `e9b8cc68d8cc92e9130bfce38983172f203c9021`; its hosted E2E failures exposed invalid empty employee fields, stale mounted form defaults, and browser locator/test setup defects. Those are corrected here. Hosted checks on the new revision and merge/deployment validation remain pending.

## Evidence

- `PATH=/tmp/hris-task-bin:$PATH bash scripts/verify.sh`: **RESULT: PASS (exit 0)**, uninterrupted on the final code revision.
- Backend: **737 passed**, ruff clean, mypy 0 errors (98 files), migration upgrade clean and no drift.
- Frontend: **116 files / 411 tests passed**, TypeScript 0 errors, ESLint 0 errors / 10 report-only warnings, build successful.
- Generated MAP in sync; `git diff --check` clean.
- Full Playwright suite against a disposable database: **59 passed, 0 failed, no retries**, one worker. This run covers all Batch 1 flows and existing journeys. A subsequent optional-empty-field no-change normalization and its Vitest assertion are covered by the final full gate; hosted E2E will confirm the pushed revision.
- Browser journeys exercise employee create/edit/archive, salary lifecycle and missing-salary recovery through payroll generation, leave policy/enrollment, approve/reject/cancel with calendar and ledger readback, permission denial and reload persistence.

The existing `hris-ui-qa-e2e` PostgreSQL container on port 55603 was reused with a separate disposable database. Owned application servers and database were removed, and the container restored to its original stopped state. The full gate removed its own temporary PostgreSQL container. No production writes were made.

## Scope and remaining work

Batch 1 is tested locally; it is not yet marked deployed. Employee annex/attachment UI remains deferred by design. Batch 2 (PAY-01/02/04–08 statutory configuration and payroll persistence) and Batch 3 (QA-06 role lifecycle, QA-07 relationship labels) remain open. Do not describe the entire backlog as resolved.

Unrelated untracked `DESKFLOW_PLAN.md`, `docs/bugs/`, and `scripts/__pycache__/` remain preserved and excluded from the PR. No test applies to this documentation-only checkpoint update.

Next: push this commit, verify local/remote/PR head equality, check hosted CI, independently review and merge through the protected PR, then validate the deployment pipeline and read-only live smoke checks. Codex owns merge/deployment; Kilocode restrictions do not prohibit Codex delivery. Continue remaining batches in separate worktrees from current main after Batch 1 lands.
