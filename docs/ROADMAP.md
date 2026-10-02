# HRIS Cleanup Roadmap

This document is the authoritative numbered roadmap for the HRIS cleanup project.

Task numbers are stable identifiers and must not be renumbered or replaced by phase trackers.

Status values describe the current project state and should be updated only with repository-backed evidence.

See docs/MAP.md for generated repository structure information.
See docs/STATUS.md for the current implementation/status snapshot.

---

## Ground rules

- Task numbers #1–#94 come from the original project handoff and are historical
  identifiers. Never renumber, merge, split, or delete them.
- The machine trackers `docs/roadmap/backend-phases.json` and
  `docs/roadmap/frontend-phases.json`, and the port plans
  `backend/REWRITE_ROADMAP.md` / `frontendv3/REWRITE_ROADMAP.md` /
  `analysis/08-rewrite-plan.md`, describe feature phases — they are **not** the
  authoritative numbered cleanup roadmap and never override this file.
- Roadmap task numbers are not GitHub PR numbers. For example roadmap #29/#30
  (stale documentation) are unrelated to Dependabot PR #29/#30.
- Allowed statuses: `DONE`, `OPEN`, `IN PROGRESS`, `SKIPPED / NOT APPLICABLE`,
  `DEFERRED / REMOVED FROM ACTIVE SCOPE`, `NEEDS RECONCILIATION`.
- Every status change must cite evidence (PR, commit, command output, or CI run).

Baseline for the statuses below: `origin/main` at `f8b890d` (2026-09-29),
reconciled 2026-09-29 after PRs #53 (`2c828e3`, MAP generator correctness),
#54 (`0c68537`, roadmap versioning / source-of-truth docs) and #55
(`f8b890d`, template-residue round 1) merged. Re-reconciled 2026-09-30 after
the final-cleanup Batch B1 PR (#56, `62f1372`) and Batch B2 PR (#57,
`a4f33d3`) merged. Item statuses below change only
where the merged repository state directly proves it; pending PRs are cited,
not assumed. (Naming: this document's internal "Batch A / B.1 / B.2 / B.3 /
C / D" labels are the earlier documentation-plan batches — MAP generator,
source-of-truth audit, PR #54 doc reconciliation, residue cleanup, operational
docs, verification hardening. The dot-free "Batch B1/B2/..." labels below refer
to the post-audit final-cleanup implementation plan, merged as GitHub PRs #56
and #57 respectively.)

---

## Status summary

| Task | Status |
| ---- | ------ |
| #1 | DONE |
| #2 | SKIPPED / NOT APPLICABLE |
| #3 | DONE |
| #4 | DONE |
| #5 | DONE |
| #6 | DONE |
| #7 | DONE |
| #8 | DONE |
| #9 | DONE |
| #10–#15 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #16 | DONE |
| #17 | DONE |
| #18 | DONE |
| #19 | DONE |
| #20 | DONE |
| #21 | DONE |
| #22 | DONE |
| #23 | DONE |
| #24 | DONE |
| #25 | DONE |
| #26 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #27 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #28 | DONE |
| #29 | DONE |
| #30 | DONE |
| #31 | DONE |
| #32 | DONE |
| #33 | DONE |
| #34 | DEFERRED / REMOVED FROM ACTIVE SCOPE |
| #35 | DEFERRED / REMOVED FROM ACTIVE SCOPE |
| #36 | DEFERRED / REMOVED FROM ACTIVE SCOPE |
| #37 | DEFERRED / REMOVED FROM ACTIVE SCOPE |
| #38 | DEFERRED / REMOVED FROM ACTIVE SCOPE |
| #39 | DONE |
| #40 | NEEDS RECONCILIATION |
| #41 | SKIPPED / NOT APPLICABLE (not a repository concern) |
| #42 | DONE |
| #43 | DONE |
| #44 | DONE |
| #45 | DONE |
| #46 | DONE |
| #47 | DONE |
| #48 | DONE |
| #49 | DONE |
| #50 | DONE |
| #51 | DONE |
| #52 | DONE (documented rollback limitation; history preserved) |
| #53–#55 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #56 | DONE |
| #57 | DONE |
| #58 | DONE |
| #59 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #60 | DONE |
| #61 | DONE |
| #62 | DONE |
| #63 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #64 | DONE |
| #65 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #66 | DONE |
| #67 | DONE |
| #68–#71 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #72 | DONE |
| #73 | DONE |
| #74 | DONE |
| #75 | DONE |
| #76 | DONE |
| #77 | DONE |
| #78 | DONE (history preserved by owner decision) |
| #79 | DONE |
| #80 | DONE |
| #81 | DONE |
| #82 | DONE |
| #83 | DONE |
| #84 | DONE |
| #85 | DONE |
| #86 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #87 | DONE |
| #88 | DONE |
| #89 | DONE |
| #90 | DONE |
| #91 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #92 | DONE |
| #93 | DONE |
| #94 | SKIPPED / NOT APPLICABLE (personal/local tooling, not repo-owned) |

---

## Task notes and evidence

Only tasks whose wording or evidence is recorded in the authoritative handoff /
session history appear here. For tasks marked DONE with no note, the status
comes from the handoff's authoritative status list; the original wording was not
preserved in any recoverable artifact, and no wording is invented here.

### #2 — Live dashboard — SKIPPED / NOT APPLICABLE
Owner decision: the live dashboard is not actively used; no implementation
effort is to be spent.

### #5 / #82 — Historical 273-uncommitted-changes local folder situation — DONE
Completed read-only worktree investigation; historical WIP classified and
recoverable; main checkout clean; no stale worktree prune candidates at the
time of the investigation.

### #20 — Dockerfile still used `npm install` instead of `pnpm` despite `pnpm-lock.yaml` existing — DONE
Evidence: PR #43; `frontendv3/Dockerfile` uses Corepack + pnpm 11.17.0,
`pnpm install --frozen-lockfile`; production Docker build passed.

### #22 - Dependabot backlog - DONE
Owner chose runtime and deployment-action migrations on 2026-10-02.
All thirteen remaining proposals were reviewed individually and replaced by
PR #68, merged as 7e941373ae5bc290b5bacd297f9c044139dc8063.
Final verification: 519 backend tests on Python 3.14, 270 frontend tests,
zero mypy errors, no migration drift, both production Docker builds passed.
Upgraded GitHub CI and deployment run 36980650229 succeeded.
PRs #1/#2/#9/#18/#27/#28/#29/#30/#47/#48/#49/#50/#51 are confirmed CLOSED.
See docs/plans/runtime-upgrades-2026-10-02.md for individual dispositions.

### #25 / #58 — Backend mypy and frontend ESLint error cleanup — DONE
Evidence: PRs #37, #39, #40, #41. Current verified state on origin/main
(re-measured on `f8b890d` via `scripts/verify.sh`, 2026-09-29): mypy
`Success: no issues found in 97 source files`; ESLint `0 errors / 2 warnings`
(both `react-hooks/incompatible-library`). The 3 unused eslint-disable
warnings reported at the bf2a479 baseline no longer reproduce. Do not
describe the old error counts (or the bf2a479 warning count) as current.

### #28 — scripts/verify.sh — DONE
`scripts/verify.sh` exists (commit 4cc67e8) and runs ruff, mypy, alembic
drift-check, pytest, tsc, eslint, vitest, MAP drift, and frontend build with a
PASS/FAIL summary. The report-only comments inside it that named already-fixed
gaps were corrected in final-cleanup Batch B2, merged as PR #57 (`a4f33d3`) —
mypy/eslint stay REPORT-ONLY by policy, no longer labeled as known gaps.

### #29 / #30 — Stale documentation / AGENTS information — DONE
Original concern: migration counts, test counts, router counts, coverage
information, old `frontend/` references in AGENTS.md and related docs.
Batch B.1 (audit, 2026-09-28) produced the findings; Batch B.2 was merged as
PR #54 (`0c68537`), applying the corrections to AGENTS.md, docs/STATUS.md,
README.md, and creating docs/ROADMAP.md, docs/README.md, and the
docs/roadmap/SOURCE_OF_TRUTH.md supersession banner. The post-merge audit
(2026-09-29) found residual drift introduced by the events after the B.2
baseline `bf2a479`: the eslint "5 warnings" claim (re-measured on `f8b890d`:
0 errors / 2 warnings, cached and `--no-cache`), STATUS.md describing merged
PR #53 as open, and the ROADMAP baseline note. Those corrections merged as the
final-cleanup Batch B1 PR (#56, `62f1372`). Note: unrelated to Dependabot
PR #29/#30.

### #31 / #32 / #33 — Feature-development process documentation — DONE
Handoff: "Feature-development process documentation: Feature-dev.md cleanup,
one-plan-per-task, fresh-session-per-step discipline. Previously incomplete.
Determine current state." Current state (re-verified 2026-09-29 from
origin/main): `.kilo/` is gitignored by repository convention
(`.gitignore:13` — verified via `git check-ignore -v .kilo/commands/...`),
the host-local `feature-dev.md` is technology-generic by design and contains
no one-plan-per-task or fresh-session-per-step text, and no tracked
repository doc carried the end-to-end process. Resolution: new tracked
`docs/feature-development-workflow.md`
(worktree from origin/main, dedicated branch, one plan per task, fresh
session per step, evidence-first, verify-before-PR, migration round-trip
rule, no direct work on main, no mixing unrelated cleanup), cross-linked from
AGENTS.md's documentation map; `.kilo/commands/feature-dev.md` remains
host-local by convention (see #93). Merged via the Batch B1 PR (#56,
`62f1372`). (Note: GitHub
PR #32 is the AGENTS evidence-rule PR — that delivered roadmap task #73, not
task #32. Do not conflate PR numbers with task numbers.)

### #34–#38 — Nightly automation / restore-drill tasks — DEFERRED / REMOVED FROM ACTIVE SCOPE
Explicit owner decision. Do not implement. Do not renumber anything after them.

### #39 - Fresh Playwright E2E setup - DONE
The dedicated E2E workflow runs all 25 specs on pull requests and main
against an isolated PostgreSQL database, with Python 3.14 and Node 26.
Verified 2026-10-02: 40 browser tests passed on a fresh database;
scripts/verify.sh passed with 707 backend tests, 280 frontend tests,
zero mypy errors, and no migration drift. CRUD journeys assert persistence
and deletion. See docs/plans/e2e-ci-completion.md for coverage and limits.

### #40 — Secrets committed to Git history — NEEDS RECONCILIATION
Filename-level scan found no tracked secret-bearing files (`.env` is
untracked/ignored; no `.env` additions across history). A content-level
history scan (gitleaks-style, metadata-only report) has **not** been run, so
this is not closable yet. Related: `.copier/.copier-answers.yml` is tracked and
contains template-era credential-shaped values; treat under this task / #88 —
do not print the values.

### #41 — Techrostrum pay dispute — SKIPPED / NOT APPLICABLE
Explicitly unrelated to this repository.

### #42 / #43 / #44 / #45 / #46 - Documentation / MAP work - DONE
Existing generated MAP and workflow validation remain in place.
The six Batch C stubs now contain architecture boundaries, recorded decisions,
current module responsibilities and explicit feature gaps, plan conventions,
real test/CI execution instructions, and a provenance-preserving archive index.
No historical design documents were moved or rewritten.
STATUS and AGENTS are refreshed from this finish pass's verification evidence.

### #52 — Migration `b9748b3e7b5c` leaves orphaned PostgreSQL enum types after downgrade — DONE (documented limitation)
Owner decision on 2026-10-02: preserve the chain and document rollback limits.
See docs/runbooks/migration-limitations.md and the migration-history decision.
Confirmed: its `upgrade()` creates 8 enum types (`genderscope`, `holidaytype`,
`leavecadence`, `leaveledgersource`, `leaverequesteventtype`, `leavestatus`,
`maritalstatusscope`, `observeweekendas`); the `downgrade()` drops the tables
but never `DROP TYPE`s them (correct pattern exists in `bc349a74ea22` for
`notificationtype`). **The earlier claim "non-destructive leak; re-upgrade
works" is FALSE — reproduced on `a4f33d3` (2026-09-30, throwaway
postgres:18):** downgrade one step to `b9748b3e7b5c`, all 8 enum types remain
in `pg_type`, and re-running `alembic upgrade b9748b3e7b5c` fails with
`psycopg.errors.DuplicateObject: type "leavecadence" already exists`. The
same round-trip failure was reproduced for the other two orphan-enum
downgrades MAP flags (`7286295e0903`: orphan `employeestatus`, re-upgrade
`DuplicateObject: type "employeestatus" already exists`; `d4b4a4d0b4a1`:
after downgrading past it, re-upgrading to head fails `DuplicateObject: type
"cutofftype" already exists`). A separate, distinct failure exists at the
downgrade base `10fc690ffb09`: its auto-generated `downgrade()` contains
`op.drop_constraint(None, 'user', type_='foreignkey')` and fails immediately
with `sqlalchemy.exc.CompileError: Can't emit DROP CONSTRAINT ... it has no
name` (unnamed FK constraint), so even `alembic downgrade -1` from that
revision cannot run. Do not rewrite historical migrations cosmetically;
either add a corrective migration with tested upgrade/downgrade or document
the limitation with evidence. Batch A (PR #53, merged as `2c828e3`) landed
report-only generator detection of this class of anomaly — current `docs/MAP.md`
lists 3 orphaned-enum downgrades (`7286295e0903`, `b9748b3e7b5c`,
`d4b4a4d0b4a1`) — but does not fix the migrations; the remediation decision
is resolved by documentation, not a migration rewrite. Migration files were deliberately NOT touched in this
reconciliation; the failures above are recorded as reproduced evidence.

### #60 — Production runners on ubuntu-26.04 — DONE
Evidence: PR #45 (Playwright 1.59.1 → 1.62.1) and PR #46 (deploy workflow
runners `ubuntu-26.04`) merged; PR #44 obsolete/closed. CI passed on real
ubuntu-26.04 runners.

### #61 / #62 - Deployment verification and service health - DONE
Implemented in this PR: native Traefik ping and frontend HTTP healthchecks,
with the deploy job waiting for backend, frontend and Traefik to become healthy.
The verify job runs scripts/verify-deployment.py: API health JSON, anonymous
GET /users/me returning 401, hidden docs returning 404, frontend and sign-in
application shells, and HTTP-to-HTTPS redirects for both hosts. Contract failure
tests exercise broken authorization, docs exposure, frontend shell, redirects
and health responses. These probes use no production credentials or writes.
Successful authenticated business flows are covered in isolated E2E tests,
not by logging into production.


### #67 — Payroll migration review — DONE
Review found no destructive `upgrade()` operations in the payroll migration.

### #72 — Operational runbooks — DONE
Merged via PR #31; located at `docs/runbooks/` (deploy, rollback, migrations,
backup-restore).

### #73 — AGENTS.md evidence requirement — DONE
Merged via PR #32; now AGENTS.md §8 "Evidence requirement".

### #74 — Payroll calculators require login — DONE
`POST /api/v1/payroll/runs/generate` requires `payroll:add`
(`require_permission`); regression tests added in PR #36.

### #76 — CodeQL — DONE
`gh api .../code-scanning/alerts?state=open` returns `0` open alerts
(verified 2026-09-28/29).

### #77 - Unused dependencies - DONE
Repository-wide backend reference checks found ReportLab and its type stubs
only in dependency declarations. They are removed from the manifest and lock.
PyMySQL remains required by scripts/etl_mysql_to_postgres.py and its tests;
it is deliberately retained as ETL-only tooling. Full verification and image
builds validate the reduced dependency graph in this dependency PR.

### #78 — Three-migration salary-constraint history — DONE
Investigated (Batch A reconciliation): `f176e167c8e7` changed the employee
salary unique constraint to (employee_id, effective_date); `54ff6e36652b`
reverted it; `3f0e3e733925` (head) re-applied it. Net final schema state is
correct and `alembic check` passes — no correctness bug, single head.
Owner decision on 2026-10-02: preserve history. The migration-history
decision and migration-limitations runbook record the provenance and final
schema; no historical migration was rewritten.

### #79 — Calculator test assertions — DONE
`test_calculator.py` asserted with `pytest.approx(x, abs=0.01)` on
share/total fields and did not assert full response shapes or boundary rows.
Tighten assertions (requires live-DB run). Update 2026-10-02 (branch
`test/payroll-calculator-assertions-v2`): `backend/tests/payroll/test_calculator.py`
strengthened to assert exact two-decimal values (replacing `approx`),
full response-key sets, employee+employer==total relationships, boundary rows
(at/just-below/above each bracket min/max, clamp-to-min/max, half-even rounding),
batch contributions with taxable==gross−employee-side, and validation-rejection
422s against the application's real ErrorBody envelope (`error.message ==
"Request validation failed"`) rather than FastAPI's default list shape. Contract
findings pinned by the tests: bracket-list endpoints serialize Decimal columns
as JSON strings (e.g. `"5.000"`, `"2.000"`) and ignore an `_effective_date` query;
`calculate_bir_tax` adds `base_tax` on every traversed bracket row, not only the
final one. No production calculator/route logic changed. Existing authentication tests
for all five calculators and authenticated success are preserved. Verification
evidence is recorded in the implementation PR.

### #80 - Audit retention job - DONE
Implemented bounded daily retention in app.audit.retention and a dedicated
Compose service. Owner chose 90 days on 2026-10-02 and explicitly required
deletion to remain disabled until enabled. Default dry runs preserve data;
enabled runs delete at most 1000 old rows per day. Cutoff, default-disabled,
batch-size and invalid-policy cases are tested. No production enablement.
See docs/runbooks/audit-retention.md for activation and backlog handling.

### #81 - GET-route authentication coverage - DONE
Behavioral HTTP tests now parameterize every registered production GET API
route from the FastAPI inventory: 90 protected paths each reject missing and
malformed bearer credentials with 401. The one intentionally public GET,
health-check, returns 200 without credentials; local-only support is excluded.
Existing static authentication/permission dependency checks and live module
403 cases remain in place. New routes are included automatically.
Verification on Python 3.14: scripts/verify.sh PASS, 701 backend tests,
270 frontend tests, zero mypy errors and no migration drift.

### #83 - OpenAPI JSON / docs / redoc exposure - DONE
PR #59 disabled docs outside local environments; PR #61 fixed their typing.
Current production checks on 2026-10-02 returned HTTP 404 for /docs, /redoc,
and /api/v1/openapi.json. The deployment verifier now continuously checks all
three. API health and anonymous authentication probes returned 200 and 401.


### #84 — `.gitattributes` — DONE
Present and tracked at repo root: `* text=auto` and `*.sh text eol=lf`.
Minimum baseline satisfied; mass rewrites unnecessary.

### #85 — Worktree cleanup — DONE
Historical investigation concluded the worktrees were acceptable and
`git worktree prune --dry-run` was silent. Re-verified 2026-09-29: the dry run
now reported **one** stale registration (`/tmp/kilo/notif-test-fix` — gitdir
points to a non-existent location) belonging to the already-merged PR #52
branch. Pruned 2026-09-30 with owner authorization in this task:
`git worktree prune` removed exactly `worktrees/notif-test-fix` (dry-run
before: `Removing worktrees/notif-test-fix: gitdir file points to
non-existent location`; dry-run after: silent, exit 0). All valid worktrees
remain registered (`git worktree list` after prune still shows the main
checkout and every live branch worktree; none was touched).

### #87 — Nex N2.5 Pro — DONE
Established status per the authoritative handoff list.

### #88 — Secrets / environment / AI-prompt safety documentation — DONE
Historic state: AGENTS.md had no explicit rules section for secrets, env vars,
production credentials, AI prompts, or logs. Resolution merged in the
Batch B1 PR (#56, `62f1372`): new AGENTS.md §9 "Secrets / Environment /
AI-prompt Safety (policy)" — documentation-only, explicitly stating there is no
secret-scanning hook or CI gate enforcing it yet (`gh api` on the repo confirms
secret scanning is disabled: "Secret scanning is disabled on this repository";
roadmap #40/#92 track the missing tooling). It does not claim technical
enforcement. The `.copier/.copier-answers.yml`
credential-shaped values remain held under #40 (do not remove here).

### #89 — Local main movement — DONE
Per the authoritative handoff status list.

### #90 — Template leftovers — DONE (round 1 merged #55; round 2 merged #56)
Round 1 merged as PR #55 (`f8b890d`), removing exactly: `copier.yml`,
`.copier/update_dotenv.py`, `hooks/post_gen_project.py`,
`.github/labeler.yml`, `release-notes.md`, `backend/requirements.txt`,
`backend/railway.toml` (verified via `git show --stat f8b890d`: 7 files,
994 deletions). Round 2 merged as the Batch B1 PR (#56, `62f1372`); re-verified
2026-09-30 on `a4f33d3` that the round-2 targets are absent from
`git ls-tree origin/main`. Classification from the Batch B.1 audit (2026-09-28) of the
remaining candidates, with per-file evidence re-gathered on `f8b890d`
(2026-09-29):
- Removed (round 2, final-cleanup batch B1 — branch
  `chore/b1-docs-process-residue`): `.github/FUNDING.yml` (funds upstream
  `tiangolo`, and `gh repo view` shows `fundingLinks` still pointing at
  github.com/tiangolo), `.github/ISSUE_TEMPLATE/config.yml` +
  `privileged.yml` (route questions to
  `github.com/fastapi/full-stack-fastapi-template/discussions` and gate on
  "You are @tiangolo"; `gh api` shows `discussions.totalCount=0`,
  `issues.totalCount=0`), `.github/DISCUSSION_TEMPLATE/questions.yml`
  (GitHub Discussions are disabled on this repo: `hasDiscussionsEnabled:
  false`), `scripts/test.sh` + `scripts/test-local.sh` (upstream
  docker-compose test drivers with zero tracked references; superseded by
  `backend/scripts/tests-start.sh` + `scripts/verify.sh`).
- Rewritten, not removed: `development.md` (its Adminer/Mailcatcher/Traefik
  content maps to real services in `compose.yml`/`compose.override.yml`; only
  the false commands were fixed — `bun run dev` → `pnpm dev`, `biome check`
  hook line removed, `localhost.tiangolo.com` example generalized),
  `backend/README.md` (kept the useful uv/compose/migrations/email-template
  guidance; corrected the paths proven absent: `app/crud.py`, `app/api/`
  package, `app/core/db.py`, `app/alembic/versions/`, and the "VS Code
  configurations already in place" claim — 0 tracked `.vscode/` files),
  `SECURITY.md` (upstream `security@tiangolo.com` contact replaced with a
  repository-appropriate private-reporting process; no invented address).
- Retained deliberately: root `package.json` (its only script, `roadmap`, is
  an HRIS-specific wrapper for the docs phase tracker; only the stale `name`
  was renamed), `docs/roadmap/SOURCE_OF_TRUTH.md` (keep with supersession
  banner), `.copier/.copier-answers.yml` (do NOT remove — its disposition
  belongs to the #40/#88 security-history decision).
- Local untracked cruft on the dev host remains out of scope for repo state:
  empty `frontend/blob-report/` and `frontend/test-results/` directories
  (0 tracked files); removing them is a host action, not a PR change.

### #92 — CI config-check job — DONE
`.github/workflows/ci.yml` now contains a `ci-config-check` job alongside
`frontend` and `backend` (re-verified 2026-09-30 on `a4f33d3`: `grep -n
ci-config-check .github/workflows/ci.yml` matches at line 15). Implementation
merged via the Batch B2 PR (#57, `a4f33d3`).
Batch B2 (branch `chore/b2-ci-verification-hardening`) submitted the smallest
maintainable check: a new `ci-config-check` job runs
`scripts/check-ci-config.sh`, which fetches actionlint **1.7.12 pinned by
version AND sha256** (linux amd64/arm64 digests recorded in the script; the
binary is cached under gitignored `.cache/actionlint/` and re-verified on
use) and validates every workflow under `.github/workflows/` — YAML
structure, `${{ }}` expressions and context access, `needs` job references,
action inputs/outputs, reusable-workflow calls, runner labels, and embedded
shell (via shellcheck when present). `.github/actionlint.yaml` declares
`ubuntu-26.04` as an accepted runner label because actionlint 1.7.12's
bundled label table predates it — the label is real (roadmap #60, PR #46
migrated the runners to it). Evidence (2026-09-29, local run): bare
actionlint 1.7.12 flags every `runs-on: ubuntu-26.04` line [runner-label]
without the config and exits 0 with it, while still catching an injected
bad `needs:` reference ([job-needs], exit 1). The job is NOT added to the
`Main Branch Rules` ruleset's required status checks (only `backend` /
`frontend` are required — verified via `gh api .../rulesets`); promoting it
to a merge gate is an owner decision. Dependabot label hygiene:
`.github/dependabot.yml` requests `labels: [dependencies, internal]` but the
repo only had `internal` (verified `gh label list`); the `dependencies`
label was created 2026-09-29 via `gh label create dependencies --color 0366d6
--description "Pull requests that update a dependency file"` (repo-settings
change, verified with `gh label list`), so new Dependabot PRs now carry both
configured labels. Existing PRs were not relabeled; disposition of open
Dependabot PRs remains #22's owner decision.

### #93 — Reusable Kilocode command file — DONE (decision resolved by evidence; delivered via Batch B1 PR #56)
`.kilo/commands/feature-dev.md` exists but is untracked; decide commit vs keep
local (overlaps #31). Resolved 2026-09-29 on repository evidence:
`.gitignore:13` ignores `.kilo` (verified with `git check-ignore -v
.kilo/commands/feature-dev.md`), so ignoring it IS the established repository
convention, and this batch's rule is not to force-track what the repo
deliberately excludes. Decision: keep the command host-local; the reusable
workflow the item intended is delivered instead in tracked
`docs/feature-development-workflow.md` (the #31–#33 deliverable), cross-linked
from AGENTS.md §1's documentation map. No personal paths are included. If the
owner later wants `.kilo/` actually tracked, that is a deliberate un-ignore
decision outside cleanup scope.

### #94 — Helper scripts (`~/bin/pr-evidence`, `~/bin/prod-check`) — SKIPPED / NOT APPLICABLE
Owner decision (2026-09-30): `~/bin/pr-evidence` and `~/bin/prod-check` were
**personal/local convenience tooling on the operator's host, not
repository-owned functionality.** They were never tracked: `git log --all
-- '*pr-evidence*' '*prod-check*'` returns no commits. They no longer exist on
this host either (`ls ~/bin` → "No such file or directory"; re-verified
2026-09-30, consistent with the 2026-09-29 re-check). Decision: **do not
recreate them in the repository** — the repo already provides equivalent
evidence/verification workflows through `scripts/verify.sh` (single entry
point for the full check matrix, PR #34), the AGENTS.md §1.5 mandatory-testing
policy and §8 evidence requirement (the rules those helpers used to enforce by
habit), and `docs/feature-development-workflow.md` (the tracked, repository
process those helpers were a personal shortcut for). Item closed as not
applicable to repo scope.

### Numbers not recorded in the handoff status list
#10–#15, #26, #27, #53–#55, #59, #63, #65, #68–#71, #86, #91: no wording and
no status were preserved for these numbers in any recoverable artifact. They
remain **NEEDS RECONCILIATION** — the owner must restore their definitions.
They are deliberately not invented, deleted, or renumbered.

### DONE per the authoritative handoff list (wording not preserved)
#1, #3, #4 (grouped in handoff as #4/#50/#51), #6, #7 (grouped as #7/#8/#9),
#8, #9, #16 (grouped as #16/#17/#18/#19), #17, #18, #19, #21, #23, #24,
#47, #48 (grouped as #48/#49), #49, #50, #51, #56 (grouped as #56/#57), #57,
#64, #66, #75, #89. Status is authoritative; wording unknown.
