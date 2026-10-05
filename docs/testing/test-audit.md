# Test and runner audit

Audit continued on PR #81's `codex/testing-policy-audit` branch, based on its actual head `514de7592ae711005461f1f78a3a09211c5410e5` (2026-10-05). The main checkout's untracked files were preserved. Counts in previous snapshots were treated as historical and refreshed only after the final gate.

## Findings and changes, ranked by impact

### High: dormant E2E seed lifecycle could hide setup/cleanup failures

`frontendv3/playwright.config.ts` did not register `e2e/global-setup.ts` or `global-teardown.ts`; the configured suite instead seeds the regular account through `backend/scripts/seed_e2e.py` and creates domain state in specs/helpers. The global hooks and `fixtures/api.fixture.ts` were dead code: no configured hook/import/fixture consumers. Removed those uncalled files and fixture exports. No browser tests or assertions were removed; authentication, domain setup and persisted readback remain in the active path.

The active user seed previously allowed setup errors to propagate without clear dependency context. It now fails with an actionable seed error and a regression test injects a create-user failure. The local runner checks database readiness and expected placeholder container configuration, bounds setup and suite commands, records per-run result paths, and reports database/container cleanup failures instead of swallowing them. Fault-injection tests cover setup failure, cleanup failure, a pre-existing running container and SIGTERM during setup. Only the randomly named database created by this runner is dropped; a shared container is stopped only if it was stopped before this run.

### High: browser outputs and worker/retry policy were shared or inconsistent

Playwright previously wrote fixed report/state paths and enabled two hosted retries while local QA used zero. Reports/artifacts now use a validated run-specific directory; local and hosted runs use zero retries and a stable run ID. Local workers are configurable (1–4), with a default of **1** on this 4-vCPU, 3.83-GiB WSL host. CI uses 2 workers on its hosted runner. This avoids forcing parallel browser pressure on constrained developer machines while allowing the larger CI host to use measured parallelism.

### Medium: unused test scaffolding increased setup surface

Removed only the unregistered global hooks and unused API fixture. No pytest, Vitest or Playwright behavioral test was consolidated or deleted: similar CRUD flows protect distinct domain associations, permissions, UI behavior or persisted state. Backend authorization/concurrency checks, Vitest frontend behavior checks and Playwright integrated journeys remain complementary layers. Existing payroll lost-response/idempotency, attendance isolation, money/date and role-protection cases remain in place. This audit did not establish exhaustive boundary coverage across every domain; add cases when a concrete risk or gap is identified.

### Medium: runner failure and resource behavior lacked direct regression evidence

Added fake-tool fault injection for setup, cleanup and interruption paths plus invalid worker/timeout configuration. The local full browser run is serialized by a lock and uses a unique throwaway database. E2E contains no arbitrary fixed sleeps in the reviewed paths; fixed assertion timeouts wait for observable UI conditions. Existing Vitest timer waits cover explicit delayed behavior. Shared session-scoped pytest database setup remains intentional for that suite.

## Measurements

Host during measurement: WSL, 4 CPUs, 3.83 GiB Docker/guest memory, 2 GiB swap; Python host 3.12.3 (uv runtime Python 3.14.6), Node 24.18.0, pnpm 11.17.0, Docker 28.3.3. E2E used isolated local PostgreSQL 18, Chromium, 66 tests / 34 specs, retries 0. GNU `time` max RSS is process-level and is not an aggregate for the process tree.

| Workload | Workers | Playwright time | Runner wall | Peak process RSS | Minimum available memory |
| --- | ---: | ---: | ---: | ---: | ---: |
| Payroll slice, 7 tests (before) | 1 | 55.7 s | 73.78 s | 326,196 KiB | not sampled |
| Payroll slice, 7 tests (after) | 2 | 48.5 s | 61.50 s | 314,800 KiB | not sampled |
| Full E2E repeat, current runner | 1 | 6.6 min | 408.39 s | 388,948 KiB | 1.32 GiB |
| Full E2E repeat, current runner | 2 | 4.6 min | 289.95 s | 357,720 KiB | 0.68 GiB |

The comparable payroll slice improved ~13% in browser time and ~17% wall time at two workers. The full 2-worker run was 289.95s (66 passed in 4.6m), while the finished 1-worker run was 408.39s (66 passed in 6.6m): about 29% less wall time at two workers. During those runs, available memory reached 0.68 GiB at two workers and 1.32 GiB at one worker; swap use during the two-worker run rose from 282 to 381 MiB. On this 3.83-GiB WSL host that resource pressure outweighs local speed benefit, so local default is one worker; two remains opt-in, and CI uses two. The earlier full 1-worker timing is historical and lacked resource sampling; this current 1-worker measurement is the comparable finished candidate.

Both full E2E runs succeeded: 66 passed each, 0 retries (2 workers: 4.6m; 1 worker: 6.6m), exit 0. After each run the container was stopped as it had been before the run, and that run’s database was dropped. The final candidate was validated at the local default of one worker. The interrupted-run fault injection verified setup process termination and owned-database cleanup. Hard power loss/SIGKILL cannot be cleaned up by shell traps and remains a limitation.

## Remaining risks and prioritized backlog

1. Capture aggregate process-tree memory and comparable CI timing when a meaningful runner/configuration decision arises; current local sample showed pressure at two workers.
2. Continue risk-based review of money precision, timezone boundaries, null/empty, inactive/deleted records, retries and concurrency when changing those domains; this audit did not perform mutation testing or prove exhaustive coverage.
3. Consider further setup consolidation only when repeated mechanics create demonstrated maintenance or runtime cost. Do not remove tests based on name/count similarity.
