# PR A plan — QA-01 (import idempotency), QA-03 (uppercase adjustment actions/KPI), QA-08 (Manila daily attendance count)

Baseline: origin/main `6bd2294` (payroll PR #73 included). Branch `fix/production-qa-bugs`.
Addresses backlog IDs QA-01, QA-03, QA-08. QA-02 is withdrawn; PRs B–F deferred until this PR is reviewable.

## QA-01 — Attendance import: lost response after commit must be unknown/reconciled, retries must not duplicate

Codex review requirements and adopted contract:

1. **Race-safe duplicate protection.** SELECT-then-INSERT is not atomic. New forward
   migration `7ab12cd44e91` adds a **partial unique index** `uq_daily_time_record_source_ref_active`
   on `(employee_id, source_ref) WHERE is_deleted = false AND source_ref IS NOT NULL`.
   The DB enforces at most one active row per (employee, key) under concurrency.
   **The migration never rewrites data: a duplicate-preflight SELECT runs first and,
   if any active (employee_id, source_ref) duplicate exists, it raises
   `RuntimeError` with a per-identity diagnostic (offender rows + ids) and leaves
   every row untouched (verified live: two duplicate rows inserted at
   `3f0e3e733925` → `upgrade head` exits 1, rows still 2 active, version unchanged;
   after deliberate cleanup `upgrade head` succeeds; `downgrade -1`/`upgrade head`
   cycle clean; `alembic check` reports no drift).** `create_dtr` runs inside
   `session.begin_nested()` (SAVEPOINT): a concurrent duplicate surfaces as
   `IntegrityError` → rollback to savepoint → re-SELECT the winner → replay path.
   Proven by a **separate-psycopg-sessions concurrency test** (barrier-synchronized
   parallel inserts → exactly one row, both callers reconcile).
2. **Key semantics.** `source_ref` is an opaque per-import-row identity supplied by
   the client (import batch id + row index), never an employee/login natural key.
   Replays require identical meaningful input (`login_date`, `logout_date`,
   `shift_id`): mismatch → **409** "import row changed since first attempt —
   reconcile manually", old row untouched. Empty/whitespace key → **422**.
   Ordinary manual creates (no key) are unaffected; two legitimate punches with
   distinct timestamps (same or different keys) stay distinct rows.
3. **Deleted-row policy.** No automatic replay to a soft-deleted punch: with
   uniqueness scoped to active rows, an old deleted identity lets a retry create a
   fresh row (a deliberate new import), and after a delete-then-import-different-data
   race the 409 input mismatch guards against silent overwrite. The keyless natural-key
   merge is never used; no automatic resurrection of deliberately deleted data.
4. **Authorization preserved.** The `require_permission("daily_time_record", "add")`
   dependency runs before any lookup; the replay returns the existing row without
   changing actor/computed/source columns. Rejected requests (400/404/409/422) leave
   no persisted rows. Tests: unauthorized 403; keyless manual create; actor/computed
   spoofing still ignored; replay = 200 vs first create = 201.
5. **Client contract.** Wizard attaches a stable per-row key (`dtr-import-<batchId>-r<row>`)
   kept for retry, replacement, and reconciliation. Four response classes:
   2xx → `success`; 4xx (definite server rejection — validation/permission/conflict)
   → `error` (safe to correct + retry); **5xx → `unknown`** (the server may have
   committed before failing to answer — a definite error body is NOT proof of
   non-commit); transport failure/timeout/no-response → `unknown`. While any row is
   `unknown`: CSV textarea/file replacement is blocked (editing would abandon
   committed-or-not identities), Import/Retry are disabled, and **Reconcile** posts
   the unresolved `(employee_code, source_ref)` **pairs to the bounded authorized
   endpoint** `POST /api/v1/daily-time-records/reconcile-imports` (max 200 keys per
   request, `daily_time_record:add`, row-level scope mirrors the list route) — never
   a 20-page list scan, never a natural-key guess. Verdicts: `committed` → success;
   `deleted` → retired error (never resurrected); `not_found` (absent within the
   caller's visible scope) → retryable error, retry keeps the SAME key so a late
   commit replays 200 instead of duplicating; `unresolved` (employee outside the
   caller's visibility / unknown code / reconcile API unreachable) → stays `unknown`
   — absence of permission is not absence of data. Closing the dialog with unresolved
   rows **preserves the batch in memory** (module-level recoverable slot — the page
   unmounts the wizard on close); reopening restores it with a banner, locked editor,
   and identical keys; an explicit **Discard** button abandons identities only after
   a visible warning that late commits remain in the system.
   HTTP contract: 201 first create, 200 replay; existing 45 E2E journeys assert 201
   for their fresh keys and remain green.

## QA-03 — DTR adjustment approve/reject controls and pending KPI (uppercase)

Backend DTR adjustment status is `PENDING/APPROVED/REJECTED` (leave statuses stay
lowercase and are untouched):
- `dtr-adjustments/index.tsx`: action buttons + status colors compare uppercase.
- `dashboard/services.py`: `pending_dtr_adjustments` filter uses `"PENDING"`
  (was `"pending"` → always 0).
- Update Vitest fixtures to the real API casing; add a regression asserting a
  `PENDING` row exposes approve/reject (the reproduction of the QA screenshot).

## QA-08 — Dashboard daily attendance count (real, Asia/Manila)

`_dtr_records_daily_count`: distinct `employee_id` over active, non-absent
`DailyTimeRecord` rows whose `login_date` falls in the current Asia/Manila day,
computed as a UTC window `[00:00 PST midnight, next midnight)` using
`zoneinfo.ZoneInfo("Asia/Manila")` — no server-local/timezone dependency, no
raw-row double counting. No new dependency: `python:3.14` images ship system
tzdata (verified via `docker run`), so `zoneinfo` resolves directly.
Frontend: remove the stale "Attendance tracking not live yet" hint from the DTR
tile (tile hint updated to state semantics). Pure UTC-boundary helper is
unit-tested (16:00Z previous day = Manila today; 15:59:59Z next day = Manila
today; repeated punches one employee = 1; deleted/absent rows excluded).

## Tests / deliverables

- Backend: `tests/attendance/test_import_idempotency.py` — replay (201/200),
  mismatch-409, blank-key policies, deleted-identity policy (409 + fresh key
  creates), 403-before-replay, keyless create, natural-key non-merge, no rows on
  rejections, two-session concurrency, **plus the reconcile endpoint contract**:
  committed / deleted / not_found verdicts, same-key-different-employee never
  cross-matches, unknown employee → unresolved (not not_found), >200 keys → 422,
  late-commit race: not_found → commit → retry same key → 200 replay single row,
  non-superuser settles own pair / unresolves foreign, `add` permission required
  (403 otherwise). `tests/attendance/test_dashboard_attendance_kpis.py` — Manila
  window unit + distinct-employee count incl. delete-after-import + pending
  adjustment KPI.
- Migration evidence (disposable DB, live-run): upgrade ↔ downgrade cycle,
  duplicate-preflight failure preserving data, clean re-upgrade, `alembic check`
  parity.
- Vitest (8 wizard/idempotency cases + existing 3-flow tests realigned): stable
  keys sent per row; 5xx → UNKNOWN (never definite error); transport failure →
  UNKNOWN; close/reopen restores the unresolved batch with locked editor and
  ORIGINAL keys; Reconcile posts the exact pair set (asserted request body) and
  maps all four verdicts; unresolved/reconcile-API-failure keeps UNKNOWN + retry
  blocked; Discard unlocks; 4xx stays definite error + retry-safe; 200 replay =
  success.
- Playwright (7 new specs against a real backend; all 52 suite tests pass twice):
  `attendance/dtr-import-idempotency.spec.ts` — commit-then-lost-response via
  `route.fetch()` (server really commits) then `route.abort()`; UNKNOWN state,
  server-side Reconcile settles it against the real API; exactly-one-row API
  readback; close/reopen preservation; never-reached → not_found → key-stable
  retry commits exactly one row; Discard unlocks; UI delete of the reconciled
  punch + 404 readback. `attendance/dtr-adjustment-approval.spec.ts` — PENDING
  approve persists APPROVED across reload, recomputes the DTR (logout moved to
  adjusted value via API readback), buttons gone; reject → REJECTED + DTR
  untouched. `system/dashboard-attendance-kpi.spec.ts` — distinct-employee
  Manila-today deltas: +1 new employee, second punch unchanged, one of two
  deleted unchanged, last punches deleted → baseline.
- Gate: `scripts/verify.sh` exit 0 + full Playwright suite (repeat run 52/52).

## Risks

- New import payload shape (`source_ref`) — additive optional field; manual form
  unaffected.
- `alembic check` drift if model/index definitions mismatch — gated by verify.sh.
- CI e2e uses the same config (127.0.0.1 hostnames per known lesson).
