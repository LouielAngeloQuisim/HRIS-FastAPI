# Test and runner policy

This is the detailed source of truth for tests, fixtures and test runners. Read it before changing any of them. Operational commands and environment setup live in [the testing runbook](README.md); current observations belong in [STATUS](../STATUS.md). Findings from the repository audit are in [test-audit.md](test-audit.md).

## Mandatory rules

### Design coverage around risk

- Reuse existing runners, helpers, fixtures and conventions before adding another. A new abstraction or script needs a demonstrated purpose and must have clear inputs, safe defaults, bounded execution, actionable errors and cleanup for resources it owns.
- Choose the lowest test layer that proves the behavior: unit/service tests for rules, API tests for authorization and persistence contracts, Vitest browser tests for frontend behavior, and Playwright for critical integrated workflows. Add E2E where it protects a critical user journey or a cross-boundary risk; do not duplicate the same assertion at every layer without a reason.
- Assert externally meaningful behavior, including boundary and failure cases. Protect authorization/ownership, financial calculations and rounding, persistence, dates and time zones, validation, null/empty values, inactive/deleted records, retries, idempotency and concurrency when relevant to the change. Do not mirror private implementation details in assertions.
- Keep meaningful existing coverage for permissions, financial behavior, persistence and concurrency. Test names, file counts and coverage percentages are not goals; do not add tests to hit a count.
- Prefer deterministic data and isolated state. E2E selectors should express user intent (role/label/text) where stable; use `data-testid` for controls whose accessible name is not a stable contract. Avoid fixed sleeps when an observable condition can be awaited.

### Run and diagnose efficiently

- During development, run the narrowest useful test/check after each material change. When the finished batch is ready, run `bash scripts/verify.sh` and the relevant E2E coverage once. Repeat checks when later edits affect them, a failure requires diagnosis, or the final candidate changes; do not rerun unchanged full suites just to refresh counts.
- The required gate and available layers are described in the runbook and CI. Do not silently skip required checks. Record unavailable infrastructure and skipped checks explicitly; do not present a partial gate as full verification.
- Before calling a failure pre-existing, environmental or flaky, gather evidence: reproduce on the candidate, inspect the failing output and relevant baseline/CI evidence, and make a controlled comparison when practical. One pass followed by one failure (or the reverse) is not sufficient by itself to label flakiness. Never add retries or weaken assertions to hide a failure.
- Use existing logs/timings before measuring performance. A performance claim needs a comparable before/after measure and stated host, tool versions, workload, worker count and resource conditions. Label unmeasured explanations as hypotheses. Avoid repeated full runs merely to collect the same timing evidence.

### Isolation and reporting

- Keep all QA isolated from production: use throwaway databases, placeholder credentials and loopback-only URLs. Never run CRUD tests against production or use production data/credentials in fixtures, logs or reports.
- Clean up only resources created or owned by the run, including on failure/interruption where the runner can do so. Do not delete or stop shared resources unless ownership and prior state are established. Prefer per-run unique data and databases over shared mutable fixtures.
- Report exact commands and observed results, including pass/fail counts, skips, remaining failures, environmental limitations and material coverage limits. State explicitly when a change is documentation-only and no functional test applies. Never describe a check as passing unless its output was observed in this session.

## Optional guidance

- Use parameterization when cases share one contract and each case remains named/readable. Keep separate tests where setup or failure meaning differs.
- Prefer API setup for E2E only when setup speed matters and the behavior under test is still exercised through the UI. Verify persisted state through a boundary that can catch a frontend-only illusion.
- Capture focused traces/logs on failure and retain only what helps diagnosis. Treat generated artifacts as potentially sensitive; use placeholder-only data and bounded retention.
- Keep run-level setup small and fail-fast. A seed failure must not silently turn dependent assertions into passes or leave an apparently green partial suite.

## Gate selection

The repository's `scripts/verify.sh` is the full backend/frontend verification entry point. The Playwright suite is separate; CI runs it on pull requests, while `scripts/run-e2e-qa.sh` provides isolated local runs. Use targeted commands while iterating, then the complete required gate and relevant E2E for the finished batch. The runbook documents exact commands, dependencies and safety behavior; workflow files are authoritative for hosted CI execution.
