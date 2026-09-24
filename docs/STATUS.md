# Status (generated, do not hand-edit)
Last generated: 2026-09-24, from commit 21e4ff5
Regenerate this file rather than editing it by hand.

Quick-reference snapshot of counts that change as code lands. The hand-written
rules and baselines live in AGENTS.md; this file only lists the raw numbers and
the exact commands used to measure them, so drift between the two is easy to spot.

## Backend

| Metric | Value | Command |
| --- | --- | --- |
| Alembic migrations | 23 | `ls backend/alembic/versions/*.py \| wc -l` |
| Backend test files | 43 | `find backend/tests -name "test_*.py" \| wc -l` |
| Tests collected (not executed) | 464 | `cd backend && uv run pytest --collect-only -q` (needs a repo-root `.env`; `cp backend/env_sample.txt .env` works for collection only) |
| Tests passing | unknown - run scripts/verify.sh once it exists | collect-only cannot count passes; full run not executed for this docs fix |
| HRIS employee routers | 16 | `grep -c "_router = " backend/app/employee/routes.py` (file has no `include_router`/`sub_router` tokens); see AGENTS.md §5 for mechanism |

Note: collection requires env vars (PROJECT_NAME, POSTGRES_*, FIRST_SUPERUSER*)
from the repo-root `.env`; pytest otherwise exits with code 4.

## Frontend (frontendv3)

| Metric | Value | Command |
| --- | --- | --- |
| Vitest test files under `src` | 78 | `find frontendv3/src -name "*.test.tsx" -o -name "*.test.ts" \| wc -l` |
| Vitest test files under `src/features` | 66 | same find, limited to `frontendv3/src/features` |
| Vitest green test count | unknown - run scripts/verify.sh once it exists | `vitest list` crashes in browser mode without a live browser; a full run is the only accurate count |
| Playwright E2E specs | 25 | `find frontendv3/e2e -name "*.spec.ts" \| wc -l` |
| E2E page objects | 24 | `ls frontendv3/e2e/pages/*.ts \| wc -l` |
| tsc errors | 0 | `npx tsc --noEmit` |
| eslint errors / warnings | 15 / 5 | `npx eslint .` |
| resource-delete-dialog files | 26 (25 feature-local + 1 shared) | `git ls-files \| grep -c resource-delete-dialog.tsx` |

## CI/CD

| Metric | Value | Command |
| --- | --- | --- |
| Workflow files | 2: `ci.yml`, `deploy.yml` | `ls .github/workflows/` |
| Coverage gate (`--fail-under`) | none | `grep -rn "fail-under\|coverage report" .github/workflows/` returns nothing; no `fail_under` in `backend/pyproject.toml` |

## Security

| Metric | Value | Command |
| --- | --- | --- |
| CodeQL alerts (open) | 0 | `gh api "repos/LouielAngeloQuisim/HRIS-FastAPI/code-scanning/alerts?state=open&per_page=100" --jq length` |

## Local worktrees (stale ones are visible here)

`git worktree list` on 2026-09-24 (14 entries):

```
/var/www/vhosts/hris-python                                       e31bc41 [main]
/home/lacquisim/hris-agents                                       6d4a29a [docs/agents-update]
/home/lacquisim/hris-be                                           1cd6ba8 (detached HEAD)
/home/lacquisim/hris-cleanup                                      85ee9d6 [chore/remove-old-frontend]
/home/lacquisim/hris-docs                                         c519c8c [docs/runbooks]
/home/lacquisim/hris-fix                                          7cb0676 [fix/frontendv3-head-build]
/home/lacquisim/hris-payroll-trial                                b1a3ad2 [feat/payroll-backend]
/home/lacquisim/hris-proxy                                        2f199ec [fix/proxy-headers]
/home/lacquisim/hris-security                                     24ac4f2 [chore/security-hygiene]
/home/lacquisim/hris-status                                       21e4ff5 [docs/fix-stale-numbers]
/var/www/vhosts/hris-python/.kilo/worktrees/nutritious-catamaran  21e4ff5 (detached HEAD)
/var/www/vhosts/hris-python/.kilo/worktrees/river-vibraphone      90e5b93 [river-vibraphone]
/var/www/vhosts/hris-python/.kilo/worktrees/runbooks              4bab0f0 [runbooks]
/var/www/vhosts/hris-python/.kilo/worktrees/turquoise-dedication  21e4ff5 (detached HEAD)
```

Branches already merged or abandoned (compare with `git branch -r --merged origin/main`
when pruning).
