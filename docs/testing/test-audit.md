# Test and runner audit

Audit baseline: clean `codex/testing-policy-audit` worktree at `origin/main` SHA `4f2eece1f5f0eec8a36ddd65b709fcdf7fcc4336` (2026-10-05). The primary checkout had unrelated untracked files; they were preserved. No functional test or runner changes were made in this audit. Counts in old docs/STATUS snapshots were treated as historical, not re-verified here.

## Findings ranked by impact

### High: E2E seed failures are swallowed and cleanup can look successful

- `frontendv3/e2e/global-setup.ts:74-96` catches seed exceptions, logs them and returns successfully. Seed helpers at `:15-71` also accept failed POST responses and continue with partial/empty IDs. Tests can therefore run with missing prerequisites and fail later misleadingly or pass without intended data.
- `frontendv3/e2e/global-teardown.ts:14-43` ignores failed deletes and state-file parse errors, then reports cleanup complete. This hides leaked seed records. The state is a fixed `e2e/.e2e-seed-state.json`, creating a collision risk for concurrent invocations sharing a checkout.
- Recommendation: separately plan a small fixture/runner fix: fail setup on unexpected non-success responses; make cleanup failures visible; store state per run or remove cross-run state. Add focused regression coverage and exercise failure/interruption cleanup before changing behavior.
- Measurement limit: code inspection only; no parallel runs or injected seed/cleanup failures were performed.

### High: Local and hosted E2E execute different retry/worker policies

- `frontendv3/playwright.config.ts:9-12` sets CI retries to 2 and workers to 1; local defaults to zero retries and Playwright's default worker count. `scripts/run-e2e-qa.sh:98` explicitly uses one worker and zero retries. A green hosted run can conceal first-attempt failures that the local runner exposes, and its elapsed time is not directly comparable to local QA.
- Recommendation: keep retry policy diagnostic (retain first-attempt evidence), report flaky/retried outcomes distinctly, and benchmark worker counts on isolated disposable databases before changing concurrency. Consider using one retry policy for release evidence only after the suite is measured.
- Measurement limit: no current timing artifacts found. Runtime and contention impact is a hypothesis; no wall-time/resource benchmark was run.

### Medium: Historical frontend strategy conflicts with current policy and implementation

- The previous `frontendv3/docs/testing-strategy.md` prescribed identical per-feature test filenames, minimum test/spec counts and a 90% coverage gate, and showed stale auth/setup examples. Those prescriptions conflict with current code and the risk-based requirement. It has been replaced with a reference to the policy and runbook.
- Recommendation: select cases by behavior and risk; preserve layered checks where each catches a distinct boundary (for example Vitest request/state behavior plus E2E persisted readback), and avoid rote file matrices.
- Evidence: source document contained literal lists and historical targets; current actual suites contain 58 backend Python test files, 121 frontend source test files and 68 E2E TypeScript files in this checkout. Counts are inventory only, not quality metrics.

### Medium: Repeated E2E CRUD scaffolding offers a consolidation opportunity, but not a deletion case

- Many domain specs and page objects repeat create/edit/delete flows (`frontendv3/e2e/organization/*.spec.ts`, `projects/*.spec.ts`, `hris/*.spec.ts`; page objects under `e2e/pages/`). Some validate distinct relationship chains, persistence and UI affordances, so identical-looking CRUD coverage may protect different contracts.
- Recommendation: during future changes, extract only stable repeated mechanics (e.g. parent creation) when duplication causes measurable maintenance cost; retain assertions for each domain's unique associations, authorization and persistence. Do not mass-delete similar tests based on shape alone.
- Measurement limit: static review; no mutation testing, assertion effectiveness study or test runtime attribution was performed.

### Medium: The verification script may be expensive, but no timing evidence justifies optimization

- `scripts/verify.sh:125-...` provisions disposable PostgreSQL, installs/synchronizes backend and frontend dependencies, and runs Ruff, mypy, Alembic, full pytest, TypeScript, ESLint, full browser-mode Vitest, map drift and build. This broad gate is appropriate for final evidence but costly for every edit. Local iterations can use focused runners as the policy now directs.
- `scripts/verify.sh:...` can skip DB-dependent checks when Docker is unavailable, while exiting according to its accumulated gates; the summary must be read to distinguish a full pass from skipped backend work. E2E is separate by design (`docs/STATUS.md` historical note; `.github/workflows/e2e.yml`).
- Recommendation: if run time becomes a demonstrated bottleneck, collect per-section timings and resource usage from representative clean and warm runs before changing caching, job parallelism or gate boundaries. Preserve full PR coverage.
- Measurement limit: no logs or runner timing reports were present in the checkout. Host CPU/RAM, Docker configuration, dependency cache state and suite timings were not recorded, so runtime/resource conclusions are unmeasured.

## Coverage and isolation review

- Useful overlap is present where layers answer different questions: backend/API authorization and concurrency tests prove server enforcement; Vitest checks UI permission and request/state behavior; Playwright checks critical integrated paths and persisted readback. Do not count these as redundant unless they assert the same behavior at the same boundary.
- Existing focused files cover high-risk areas such as payroll generation lost-response recovery (`frontendv3/e2e/payroll/configuration-workflows.spec.ts:47`), attendance import idempotency and account isolation, and frontend import retry/resume. Their presence does not establish full boundary coverage for all money/date/null/deleted-record cases; audit those per change and domain risk.
- Local E2E runner has loopback URL guards, unique disposable DB creation, port ownership checks, a lock, zero retries, and cleanup that drops its run DB and restores container state (`scripts/run-e2e-qa.sh`). CI uses a disposable Postgres service and placeholder variables (`.github/workflows/e2e.yml`).
- Playwright selectors include semantic roles and test IDs; arbitrary fixed sleeps were not identified in the searched E2E/config paths. Some helpers use fixed visibility timeouts, which are bounded assertions rather than sleeps.
- A fixed setup state file and swallowed errors remain the concrete E2E isolation/reliability risks above. Local runner cleanup is trapped for normal shell exit/signals, but hard termination/power loss is inherently outside shell cleanup guarantees.

## Prioritized backlog

1. Harden E2E global setup/teardown failure reporting and per-run state ownership; add fault-injection tests and interruption cleanup evidence.
2. Record CI and local section-level timing plus CPU/memory/Docker conditions over a small representative set; only then assess cache, worker, or fixture optimizations.
3. Review test quality by risk area (permissions, persistence, time zones, monetary rounding, null/empty, inactive/deleted, retry/idempotency/concurrency) as domain changes occur; add targeted cases only for demonstrated gaps.
4. Consider focused deduplication of repeated E2E setup mechanics where maintenance cost is demonstrated, preserving domain-specific contracts.
