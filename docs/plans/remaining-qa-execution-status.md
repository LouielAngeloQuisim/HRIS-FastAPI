# Remaining QA Execution Status

Updated 2026-10-05, Asia/Manila. This is the code acceptance checkpoint; live merge/deployment state is recorded in GitHub workflows and the final completion report.

## Accepted scope

| Items | Outcome | Evidence |
| --- | --- | --- |
| QA-01/QA-03/QA-08 | Previously fixed; regressions maintained | import reconciliation/owner isolation, approval/rejection, daily KPI browser journeys |
| QA-02 | Withdrawn; native date-input test artifact | historical QA notes preserved |
| QA-05/PAY-03/QA-04 | Fixed and deployed in PR #75 | employee CRUD, salary recovery/deactivation, leave policy/enrollment and request/calendar/ledger journeys |
| PAY-01/PAY-02/PAY-04–PAY-08 | Fixed in PR #76, with final PAY-08 wording follow-up in this batch | statutory configuration lifecycle, monetary SSS values, BIR open bounds/periods, real rejected-write feedback, transient preview and identity-stable generation retry |
| QA-06/QA-07 | Fixed and verified in final administration batch | role history/protection/race tests, related names after reload, unchanged persisted IDs, missing-parent fallbacks |

No reported backlog implementation remains. Deferred attachment/201-file annexes and mock-backed template demos remain outside this accepted scope. Older untracked docs/bugs/ QA artifacts are reproduction history; their OPEN labels are superseded by this acceptance checkpoint and the final release report.

## Delivery already verified

PR #75 merged as 4b94aac1539ab4ce558e77e85fc6d42ea8d2a39c. Deployment run 37257032038 passed; independent nine-check live verification passed. PR #76 merged as 4f88ec7fa850e8187bf9c5c0a4e28571a9b6890c. Deployment run 37261105896 passed CI/build/deploy/verify, post-merge E2E passed, and independent nine-check live verification passed. No production CRUD or permission changes during QA.

## Final combined acceptance evidence

Integrated origin/main 4f88ec7 into fix/batch3-administration-workflows before final testing. scripts/verify.sh RESULT PASS (exit 0): 797 backend tests; 431 frontend tests / 121 files; Ruff clean, mypy/tsc 0 errors, no migration/MAP drift, build OK; ESLint 0 errors / 7 report-only warnings. 250 API routes, 25 migrations, single head 8c12ab55d901. Full Playwright: 66/66 passed without retries using scripts/run-e2e-qa.sh, a unique disposable DB and native WSL Docker. Backend includes real two-session assignment/deactivation and generation concurrency proofs, authorized bounded labels, and seven runner URL/filter guards. Statutory form validation suite 25/25. The prior mock-boundary failure and numeric matcher type mismatch were corrected and are covered by the passing full gate.

The final administration release follows protected PR review/checks/merge and automatic deployment; Codex owns delivery. This checkpoint records acceptance, not a continuously updated deployment monitor.

## Repeatable QA and next module

See docs/testing/README.md for one-command full/per-module browser runs. The runner reuses hris-ui-qa-e2e with a unique database, owns its servers and restores the container's original state. Native Docker now responds directly in WSL; Windows CLI fallback is supported. Never run the CRUD suite against production. Use python3 scripts/verify-deployment.py for read-only live smoke.

Start a new module from current origin/main in a fresh worktree, write its plan, then add meaningful Vitest and Playwright user journeys and run the full gate before PR delivery. Preserve unrelated primary DESKFLOW_PLAN.md, docs/bugs/ and script bytecode artifacts. No test applies to this documentation-only checkpoint; all code acceptance evidence above comes from actual session runs.
