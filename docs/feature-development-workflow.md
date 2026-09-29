# Feature Development Workflow (HRIS)

This is the tracked, repository-specific process for every HRIS change —
feature, bugfix, cleanup, or documentation. It exists because the project
rules live here (AGENTS.md §1.5 testing policy, §8 evidence requirement, §9
secrets policy) and because the host-local `.kilo/commands/` directory is
deliberately gitignored (`.gitignore:13`), so tool-side command files cannot
carry the process for the team. If a local `.kilo` command disagrees with this
document, this document wins for anything that touches the repository.

This workflow is for **this** repository (FastAPI + SQLModel backend in
`backend/`, React + Vite frontend in `frontendv3/`, Docker Compose, GitHub
Actions). It assumes nothing from the original upstream template.

## The rules in one page

1. **Start from current `origin/main`.** Always
   `git fetch origin main` first, and treat `git rev-parse origin/main`
   as the baseline, not whatever the main checkout happens to sit on.
2. **Never work directly on `main`.** `main` is protected
   (`Main Branch Rules`: PR required, no force-push/deletion,
   `backend`/`frontend` status checks). Work happens in a worktree on a
   branch.
3. **One worktree per task.**
   `git worktree add -b <branch> ../hris-<short-name> origin/main`
   (a sibling directory of the main checkout) — never edit the main checkout
   itself.
4. **Branch naming:** `<type>/<kebab-topic>` with one of `feat/`, `fix/`,
   `chore/`, `docs/`, `ci/`, `test/`. One concern per branch; do not mix
   unrelated cleanup into feature work (open a separate `chore/` or
   `docs/` branch for it).
5. **One implementation plan per task/batch.** Before touching code, write
   a short plan (goal, files, tests, verification, risks). A batch/PR that
   needs a second unrelated plan is two tasks — split it.
6. **Fresh execution session per step when appropriate.** Long multi-step
   batches are executed step-by-step with a fresh session per step, each
   step starting from raw evidence (git status, the plan, the roadmap item),
   not from a previous session's memory of what it did.
7. **Investigation is evidence-based.** Read-only commands first
   (`git status`, `git log`, `grep`, `git ls-tree`, `gh` read calls). No
   conclusion without the command that proves it. Verify current state —
   documents (including this one) can be stale.
8. **No success claims without raw command evidence** (AGENTS.md §8).
   Paste actual output: test counts, PR numbers, `gh pr checks`,
   `git ls-remote`. Never "tests pass" — state "N passed, 0 failed".
9. **Implementation includes verification.** Every code change ships with
   its test(s) (AGENTS.md §1.5) and a full `bash scripts/verify.sh` run
   against the throwaway postgres container. Documentation-only changes
   state "No test needed: this is a documentation-only change" and still
   run `verify.sh` to prove nothing technical regressed.
10. **Migrations require extra verification.** New/changed migrations must
    pass `alembic upgrade head` + `alembic check` (verify.sh gates these),
    and any migration with a `downgrade()` must be round-trip tested on a
    throwaway database. Follow the pattern in
    `backend/alembic/versions/bc349a74ea22_*` (drop native enum types in
    `downgrade()`); never leave orphaned enum types behind. Production
    migrations only run through a merged PR (see `docs/runbooks/migrations.md`).
11. **PRs are opened only after verification**, never before. PR body must
    contain the raw verification evidence.
12. **The final report includes raw evidence** for every claim: baseline
    SHA, commands run, outputs, test counts, PR number/URL, CI status.
13. **Deployment happens only by merging a PR to `main`**
    (AGENTS.md §8 / `docs/runbooks/deploy.md`). Never `hris-deploy deploy`
    when a migration is pending.

## Standard task sequence

1. `git fetch origin main` → record `git rev-parse origin/main`.
2. Create worktree + branch from `origin/main` (rules 3–4).
3. Write the one-page plan (rule 5); for cleanup/audit batches, cite the
   roadmap numbers from `docs/ROADMAP.md` you are addressing.
4. Investigate (rule 7) — inspect every file before modifying or removing
   it; prove references/importers with `git grep` before any deletion.
5. Implement (smallest coherent change; colocated tests per AGENTS.md §1.5).
6. `bash scripts/verify.sh` → must exit 0; record the SUMMARY table and
   test counts. Investigate any failure; fix only what this task caused.
7. `git diff` self-review: no secrets, no machine-specific paths, no
   unrelated changes, no dependency drift unless required by the plan.
8. Commit with a focused message (`docs:` / `fix:` / `feat:` / `chore:` /
   `ci:` / `test:`), push the branch, open a PR against `main`, attach the
   evidence, and wait for `backend`/`frontend` checks.
9. Report (rule 12). Do not merge unless explicitly asked.

## Repository checkpoints

- Current state of counts/tests: `docs/STATUS.md`.
- Architecture inventory: `docs/MAP.md` (`bash scripts/gen-map.sh`).
- Numbered cleanup work: `docs/ROADMAP.md` (#1–#94, never renumbered).
- Production operations: `docs/runbooks/`.
- Secrets/env/AI-prompt policy: AGENTS.md §9.
- Frontend testing conventions: `frontendv3/docs/testing-strategy.md`.
