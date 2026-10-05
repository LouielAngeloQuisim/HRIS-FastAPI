# Remaining QA Execution Status

Updated 2026-10-05, Asia/Manila.

## Delivered

PR #75 merged as 4b94aac1539ab4ce558e77e85fc6d42ea8d2a39c. Batch 1 QA-05/PAY-03/QA-04 is deployed. Required local gate passed (737 backend, 411 frontend tests / 116 files); hosted E2E 59/59; all CI/CodeQL passed. Deployment run 37257032038 passed CI, image build, deploy and nine live verification checks. Independent read-only deployment verification also passed all nine checks. No production writes.

## Active Batch 2

Worktree /var/www/vhosts/hris-payroll-batch2, branch fix/batch2-payroll-workflows, baseline 4b94aac. Uncommitted implementation covers SSS money inputs/display, BIR nullable upper limit/period selector, inline mutation errors, statutory configuration update/deactivation, inactive-rate filtering, nonpersistent preview, generation request identity/fingerprint with PostgreSQL advisory lock, and locked unknown-outcome retries. Migration 8c12ab55d901 adds nullable generation_fingerprint; required generation payload now includes request_id UUID. Full scope PAY-01/02/04–08.

Final local evidence: scripts/verify.sh RESULT PASS (exit 0), 751 backend tests; 417 frontend tests / 117 files; Ruff clean, mypy/tsc 0 errors, no migration/MAP drift, build OK; ESLint 0 errors / 7 report-only warnings. Migration downgrade/upgrade/check passed. Full Playwright final 65/65 without retries, including a real backend permission-denied write preserving SSS form values. Earlier first full run was 63/64 with an attendance Close timeout; unchanged rerun passed 64/64. Review complete; commit/push, hosted exact-head checks and merge/deploy pending.

## Batch 3

Separate worktree /var/www/vhosts/hris-admin-batch3, branch fix/batch3-administration-workflows, same baseline. Role deactivation/assigned-role protection/assignment locking, bounded relationship labels, account-scoped caching and UI wiring are implemented but uncommitted. Focused backend 7/7 (including concurrent assignment/deactivation); focused frontend 33/33 / 15 files. One-command isolated browser runner added with guard tests. Final integration and full verification remain. QA-06/QA-07 not complete.

QA uses existing hris-ui-qa-e2e on 55603 with separate disposable databases; owned runners clean up their servers/database and restore it to stopped. Temporary Windows Docker CLI wrapper /tmp/hris-task-bin/docker enables tools without changing system configuration. Each worktree now has independent dependency environments; primary virtualenv editable package restored. Primary unrelated DESKFLOW_PLAN.md, docs/bugs/, scripts/__pycache__/ preserved.

Next: complete Batch 2 full gate/browser evidence, review, commit/push/PR, hosted checks and merge/deploy. Finish Batch 3 tests/labels, integrate merged Batch 2, run combined gates/browser coverage, review/merge/deploy and final read-only smoke. No tests apply to this documentation checkpoint itself.
