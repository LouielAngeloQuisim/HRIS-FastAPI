# Testing runbook

The mandatory coverage, isolation, diagnosis and reporting rules are in [test-policy.md](test-policy.md). Read it before changing tests, fixtures or runners. This page contains operational commands and environment notes; the authoritative execution definitions remain `scripts/verify.sh`, `scripts/run-e2e-qa.sh` and the CI workflows.

## Full verification

From the repository root:

```bash
bash scripts/verify.sh
```

This checks Ruff, mypy, migration drift, the full backend pytest suite against a disposable PostgreSQL container, TypeScript, ESLint (report-only), browser-mode Vitest, MAP drift (report-only) and the frontend build. Read the final summary: when Docker is unavailable, backend database checks are marked SKIP and the result is not equivalent to a complete backend verification.

## Targeted development checks

Use the narrowest runner that proves the changed behavior while iterating. Typical examples:

```bash
(cd backend && uv run pytest tests/<domain>/ -q)
(cd frontendv3 && pnpm exec vitest run --browser.headless src/<path>/<file>.test.tsx)
```

When the finished batch is ready, run the full required gate and relevant E2E once. Run exact commands for static checks from CI or `scripts/verify.sh` rather than maintaining a second command list here.

## Playwright local QA

Install dependencies and Chromium as appropriate for the host, then run from the repository root:

```bash
bash scripts/run-e2e-qa.sh                         # complete browser suite
bash scripts/run-e2e-qa.sh hris/batch1-workflows.spec.ts
bash scripts/run-e2e-qa.sh payroll                  # domain filter
bash scripts/run-e2e-qa.sh system/roles.spec.ts
```

The runner accepts existing paths relative to `frontendv3/e2e` or domain filters. It requires Docker, `uv`, `pnpm`, `setsid`, `flock`, Python and `curl`; Docker must already be running. It uses a disposable database and loopback services, runs serially with zero retries, and prints the path to server logs. It guards owned ports and prevents concurrent local QA runs. Do not override URLs toward production.

On hosts missing Chromium shared libraries, run `bash frontendv3/scripts/setup-playwright-libs.sh` once. The browser-mode Vitest gate sets `LD_LIBRARY_PATH` itself; when running Vitest directly, use:

```bash
cd frontendv3
export LD_LIBRARY_PATH="$(pwd)/.playwright-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
pnpm exec vitest run --browser.headless
```

## CI and production smoke checks

CI workflow files define hosted gates: `.github/workflows/ci.yml` runs backend and frontend checks; `.github/workflows/e2e.yml` runs Playwright with a disposable PostgreSQL service. E2E is a separate gate from `scripts/verify.sh`.

For production, only use the separate read-only `python3 scripts/verify-deployment.py` smoke check. Never run CRUD browser specs against production. Operational production procedures are in [runbooks](../runbooks/).
