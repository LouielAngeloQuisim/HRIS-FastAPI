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

Baseline for the statuses below: `origin/main` at `bf2a479` (2026-09-29).

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
| #22 | IN PROGRESS |
| #23 | DONE |
| #24 | DONE |
| #25 | DONE |
| #26 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #27 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #28 | DONE |
| #29 | IN PROGRESS |
| #30 | IN PROGRESS |
| #31 | IN PROGRESS |
| #32 | IN PROGRESS |
| #33 | IN PROGRESS |
| #34 | DEFERRED / REMOVED FROM ACTIVE SCOPE |
| #35 | DEFERRED / REMOVED FROM ACTIVE SCOPE |
| #36 | DEFERRED / REMOVED FROM ACTIVE SCOPE |
| #37 | DEFERRED / REMOVED FROM ACTIVE SCOPE |
| #38 | DEFERRED / REMOVED FROM ACTIVE SCOPE |
| #39 | OPEN |
| #40 | NEEDS RECONCILIATION |
| #41 | SKIPPED / NOT APPLICABLE (not a repository concern) |
| #42 | IN PROGRESS |
| #43 | IN PROGRESS |
| #44 | IN PROGRESS |
| #45 | IN PROGRESS |
| #46 | IN PROGRESS |
| #47 | DONE |
| #48 | DONE |
| #49 | DONE |
| #50 | DONE |
| #51 | DONE |
| #52 | OPEN |
| #53–#55 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #56 | DONE |
| #57 | DONE |
| #58 | DONE |
| #59 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #60 | DONE |
| #61 | OPEN |
| #62 | OPEN |
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
| #77 | IN PROGRESS |
| #78 | NEEDS RECONCILIATION (investigated; documentation-only decision outstanding) |
| #79 | OPEN |
| #80 | OPEN |
| #81 | IN PROGRESS (partial) |
| #82 | DONE |
| #83 | OPEN |
| #84 | DONE |
| #85 | IN PROGRESS (see note) |
| #86 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #87 | DONE |
| #88 | OPEN |
| #89 | DONE |
| #90 | OPEN |
| #91 | NEEDS RECONCILIATION (wording/status not recorded in handoff) |
| #92 | OPEN |
| #93 | OPEN |
| #94 | NEEDS RECONCILIATION (partial status preserved; see note) |

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

### #22 — Dependabot backlog — IN PROGRESS
Investigation (#22A/#22B) complete. 10 obsolete PRs closed as superseded
(#3 #4 #5 #6 #7 #11 #13 #14 #16 #17; earlier superseded closes #12 #15 #19 #20 #21).
Remaining work: handling decisions for the open PRs #1, #2, #9, #18, #27, #28,
#29, #30 (GitHub PR numbers, not roadmap tasks), each requiring the validation
recorded in the handoff before merge. Do not merge based on CI alone for #1,
#2, #27 (infrastructure/Dockerfile paths CI does not exercise).

### #25 / #58 — Backend mypy and frontend ESLint error cleanup — DONE
Evidence: PRs #37, #39, #40, #41. Current verified state on origin/main:
mypy `Success: no issues found in 97 source files`; ESLint `0 errors /
5 warnings` (remaining warnings were out of scope; 3 are unused-disable
directives left by the cleanup and may be trimmed later). Do not describe the
old error counts as current.

### #28 — scripts/verify.sh — DONE
`scripts/verify.sh` exists (commit 4cc67e8) and runs ruff, mypy, alembic
drift-check, pytest, tsc, eslint, vitest, MAP drift, and frontend build with a
PASS/FAIL summary. Report-only comments inside it still name already-fixed
gaps; hardening is optional Batch D work.

### #29 / #30 — Stale documentation / AGENTS information — IN PROGRESS
Original concern: migration counts, test counts, router counts, coverage
information, old `frontend/` references in AGENTS.md and related docs.
Batch B.1 (audit, 2026-09-28) produced the findings; Batch B.2
(branch `docs/source-of-truth-cleanup`) applies the corrections to AGENTS.md,
docs/STATUS.md, README.md, and creates docs/ROADMAP.md, docs/README.md, and the
docs/roadmap/SOURCE_OF_TRUTH.md supersession banner. Closes when B.2 merges.
Note: unrelated to Dependabot PR #29/#30.

### #31 / #32 / #33 — Feature-development process documentation — IN PROGRESS
Handoff: "Feature-development process documentation: Feature-dev.md cleanup,
one-plan-per-task, fresh-session-per-step discipline. Previously incomplete.
Determine current state." Current state (re-verified 2026-09-29 from
origin/main): `.kilo/` is not tracked in the repository at all —
`feature-dev.md` exists only locally and contains no one-plan-per-task or
fresh-session-per-step text. Remaining: finalize the process docs and commit
them. (Note: GitHub PR #32 is the AGENTS evidence-rule PR — that delivered
roadmap task #73, not task #32. Do not conflate PR numbers with task numbers.)

### #34–#38 — Nightly automation / restore-drill tasks — DEFERRED / REMOVED FROM ACTIVE SCOPE
Explicit owner decision. Do not implement. Do not renumber anything after them.

### #39 — Fresh Playwright E2E setup — OPEN
PR #45 (merged) made Playwright-based Vitest browser tests pass on
ubuntu-26.04 CI. However the 25 Playwright E2E specs under `frontendv3/e2e/`
are still not executed anywhere in CI (no `playwright test` invocation in
`.github/workflows/ci.yml`). Decide: run E2E in CI or scope-close with a
documented decision.

### #40 — Secrets committed to Git history — NEEDS RECONCILIATION
Filename-level scan found no tracked secret-bearing files (`.env` is
untracked/ignored; no `.env` additions across history). A content-level
history scan (gitleaks-style, metadata-only report) has **not** been run, so
this is not closable yet. Related: `.copier/.copier-answers.yml` is tracked and
contains template-era credential-shaped values; treat under this task / #88 —
do not print the values.

### #41 — Techrostrum pay dispute — SKIPPED / NOT APPLICABLE
Explicitly unrelated to this repository.

### #42 / #43 / #44 / #45 / #46 — Documentation / MAP work — IN PROGRESS
Completed so far: MAP generator exists (PR #35: `scripts/gen-map.sh` +
`docs/MAP.md`, drift check wired into verify.sh; report-only), MAP regenerated
after the payroll permission fix (PR #38), MAP content verified in sync with
origin/main@bf2a479 (Batch B.1, 2026-09-28). Batch A (MAP generator
correctness + migration anomaly reporting) is **open in PR #53 and NOT yet
merged** — its improvements must not be described as landed. Batch B.1
(source-of-truth audit) is complete. Batch B.2 (this documentation cleanup)
in progress. Remaining: #88-style policy docs, Batch C operational docs,
Batch D verification improvements.

### #52 — Migration `b9748b3e7b5c` leaves orphaned PostgreSQL enum types after downgrade — OPEN
Confirmed: its `upgrade()` creates 8 enum types (`genderscope`, `holidaytype`,
`leavecadence`, `leaveledgersource`, `leaverequesteventtype`, `leavestatus`,
`maritalstatusscope`, `observeweekendas`); the `downgrade()` drops the tables
but never `DROP TYPE`s them (correct pattern exists in `bc349a74ea22` for
`notificationtype`). Non-destructive leak; re-upgrade works. Do not rewrite
historical migrations cosmetically; either add a corrective migration with
tested upgrade/downgrade or document the limitation with evidence. Batch A
(PR #53, unmerged) adds report-only generator detection of this class of
anomaly but does not fix the migration.

### #60 — Production runners on ubuntu-26.04 — DONE
Evidence: PR #45 (Playwright 1.59.1 → 1.62.1) and PR #46 (deploy workflow
runners `ubuntu-26.04`) merged; PR #44 obsolete/closed. CI passed on real
ubuntu-26.04 runners.

### #61 / #62 — Post-deploy verification depth; frontend/Traefik health checks — OPEN
Confirmed on origin/main: deploy workflow `verify` job only curls the API
health-check and the frontend root expecting HTTP 200; `compose.prod.yml`
healthchecks exist for backend and db only (frontend and Traefik have none).
Decide whether verification must also exercise auth/redirect/protected
behavior and add missing healthchecks or document the gaps.

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

### #77 — Unused dependencies (pymysql, reportlab) — IN PROGRESS
`pymysql` is used by `backend/scripts/etl_mysql_to_postgres.py` (+ its test) —
ETL-only, document. `reportlab` has zero usage in application `.py` files —
decision outstanding on removal.

### #78 — Three-migration salary-constraint history — NEEDS RECONCILIATION
Investigated (Batch A reconciliation): `f176e167c8e7` changed the employee
salary unique constraint to (employee_id, effective_date); `54ff6e36652b`
reverted it; `3f0e3e733925` (head) re-applied it. Net final schema state is
correct and `alembic check` passes — no correctness bug, single head.
Historical awkwardness only; do not rewrite history. Outstanding: a
documentation decision.

### #79 — Calculator test assertions — OPEN
`test_calculator.py` asserts with `pytest.approx(x, abs=0.01)` on
share/total fields and does not assert full response shapes or boundary rows.
Tighten assertions (requires live-DB run).

### #80 — Audit-log retention job — OPEN
No retention/cleanup job exists in `backend/app/audit/`; a comment in
`backend/app/config/settings.py` awaits it. Decide implementation or defer
explicitly.

### #81 — GET-route authentication coverage — IN PROGRESS (partial)
Established findings: the health endpoint is intentionally public; protected
GET routes use `require_permission`/auth dependencies; complete automated
route-by-route coverage verification remains incomplete. Preserve partial
status.

### #83 — OpenAPI JSON / docs / redoc public exposure — OPEN
`backend/app/main.py` sets only `openapi_url`; FastAPI default `/docs` and
`/redoc` remain served and no route_policy/Traefik restriction was found —
publicly reachable. Owner decision required: document as intended or implement
the smallest safe protection.

### #84 — `.gitattributes` — DONE
Present and tracked at repo root: `* text=auto` and `*.sh text eol=lf`.
Minimum baseline satisfied; mass rewrites unnecessary.

### #85 — Worktree cleanup — IN PROGRESS
Historical investigation concluded the worktrees were acceptable and
`git worktree prune --dry-run` was silent. Re-verified 2026-09-29: the dry run
now reports **one** stale registration (`/tmp/kilo/notif-test-fix` — gitdir
points to a non-existent location) that prune would remove. Active worktrees
(Batch A, Batch B.2) must be preserved; awaiting owner action/decision to
prune the stale entry.

### #87 — Nex N2.5 Pro — DONE
Established status per the authoritative handoff list.

### #88 — Secrets / environment / AI-prompt safety documentation — OPEN
AGENTS.md has no explicit rules section for secrets, env vars, production
credentials, AI prompts, or logs. Documentation-only task; do not claim
technical enforcement if the result is only docs.

### #89 — Local main movement — DONE
Per the authoritative handoff status list.

### #90 — Template leftovers — OPEN (scheduled as Batch B.3)
Classification (Batch B.1, 2026-09-28):
- Definitely obsolete (tracked): `copier.yml`, `.copier/` (answers + updater),
  `hooks/post_gen_project.py`, `.github/labeler.yml` (no workflow uses it),
  template-era `development.md` (bun/Biome references), `release-notes.md`
  (808 upstream-template changelog lines), template text in
  `backend/README.md`, dead `backend/requirements.txt`, `.github/FUNDING.yml`,
  `.github/ISSUE_TEMPLATE/`, `.github/DISCUSSION_TEMPLATE/`.
- Local untracked cruft on the dev host: empty `frontend/blob-report/`,
  `frontend/test-results/` residue directories.
- Historical (keep, banner): `docs/roadmap/SOURCE_OF_TRUTH.md` (superseded).
Removal must be a dedicated, evidence-backed cleanup PR — deliberately **not**
part of Batch B.2.

### #92 — CI config-check job — OPEN
`.github/workflows/ci.yml` contains exactly the `frontend` and `backend` jobs;
no workflow-config validation (e.g. actionlint) job exists.

### #93 — Reusable Kilocode command file — OPEN
`.kilo/commands/feature-dev.md` exists but is untracked; decide commit vs keep
local (overlaps #31).

### #94 — Helper scripts (`~/bin/pr-evidence`, `~/bin/prod-check`) — NEEDS RECONCILIATION (partial)
Owner decision outstanding on whether these helpers should stay outside the
repository or move into repo tooling. Re-verified 2026-09-29: neither script
exists on this host (`ls` failed for both and for `~/bin/` itself); confirm
whether they were deleted or lived elsewhere before deciding.

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
