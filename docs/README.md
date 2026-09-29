# Documentation Index

## Authoritative sources

| Document | Role |
| --- | --- |
| [`ROADMAP.md`](./ROADMAP.md) | **Authoritative numbered cleanup roadmap** (tasks #1–#94). Stable task numbers — never renumber; update statuses only with repository-backed evidence. |
| [`STATUS.md`](./STATUS.md) | Current status/counts snapshot (hand-maintained; each number lists the command that measured it). |
| [`MAP.md`](./MAP.md) | Generated repository architecture map (routes, permissions, domain packages, frontend features, migration chain). Regenerate with `bash scripts/gen-map.sh`; do not hand-edit. Drift-checked by `scripts/verify.sh`. |
| [`../AGENTS.md`](../AGENTS.md) | Hand-written project rules, conventions, baselines, and the mandatory testing policy. |

## Historical / superseded

- [`roadmap/SOURCE_OF_TRUTH.md`](./roadmap/SOURCE_OF_TRUTH.md) — superseded
  2026-08-31 verified-state snapshot, kept verbatim for provenance. See its
  banner.

## Roadmap & design (phase trackers, not the numbered cleanup roadmap)

- [`roadmap/backend-phases.json`](./roadmap/backend-phases.json),
  [`roadmap/frontend-phases.json`](./roadmap/frontend-phases.json) — machine
  trackers for feature phases (b0–b7, f0–f7).
- [`roadmap/phase1-design.md`](./roadmap/phase1-design.md),
  [`roadmap/frontend-phase2-3-design.md`](./roadmap/frontend-phase2-3-design.md)
  — design docs.
- [`roadmap-tracker.html`](./roadmap-tracker.html) +
  [`package.json`](./package.json) — optional local visualization of the phase
  JSONs (`npm start` in `docs/` runs a live-server; `node_modules/` here is
  dev-only and gitignored).
- The repo-wide design/analysis source of truth for the rewrite itself lives
  in [`/analysis`](../analysis) and `backend/REWRITE_ROADMAP.md` /
  `frontendv3/REWRITE_ROADMAP.md` (historical port plans).

## Sections

- [`runbooks/`](./runbooks/README.md) — step-by-step operational procedures:
  [deploy](./runbooks/deploy.md), [rollback](./runbooks/rollback.md),
  [migrations](./runbooks/migrations.md),
  [backup/restore](./runbooks/backup-restore.md). Authoritative for production
  operations (AGENTS.md §8 is a summary only).
- [`architecture/`](./architecture/README.md) — design rationale (currently a
  stub section, awaiting content — roadmap Batch C).
- [`decisions/`](./decisions/README.md) — one file per decision (stub; the
  surviving invariants from the superseded SOURCE_OF_TRUTH.md §5 are candidates
  for migration here).
- [`modules/`](./modules/README.md) — per-domain current inventory (stub;
  generated inventory currently lives in MAP.md).
- [`plans/`](./plans/README.md) — active planning docs (stub).
- [`testing/`](./testing/README.md) — test conventions (see also
  `frontendv3/docs/testing-strategy.md`).
- [`archive/`](./archive/README.md) — completed/historical plans (stub).
