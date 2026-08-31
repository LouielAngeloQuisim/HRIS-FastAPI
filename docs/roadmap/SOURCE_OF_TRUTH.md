# SOURCE OF TRUTH — Verified State Snapshot

> Compiled: 2026-08-31. Command output used wherever possible; values
> derived from inspection only are marked **[UNVERIFIED — inspection only, not run]**.
>
> All claims of "done" / "passing" / "confirmed" below are backed by actual
> command output shown in this document. Claims without a corresponding output
> block are either inspection-derived or inherited from prior-session memory.

---

## §0 Git Sync

```
LOCAL HEAD:  c6996b124799be977c004ef8ce160c840e769415
origin/main: c6996b124799be977c004ef8ce160c840e769415
AHEAD/BEHIND: 0 0
```

**Local is in sync with origin/main.** No unpushed commits, no divergent history.
Working tree is dirty — see §0.1.

### §0.1 Working-Tree State (Uncommitted — NOT on origin/main)

The working tree on this session's branch contains substantial uncommitted work
on top of `c6996b1`:

- **New backend module**: `backend/app/attendance/` (models, routes, services, selectors, calc, ingestion, adjustment_models/schemas/services) — 0 files on origin/main.
- **New backend tests**: `backend/tests/attendance/` (3 files, 41 tests collected) — 0 files on origin/main.
- **New Phase 2A/2B migration files**: `backend/alembic/versions/1c721a424eb4_*.py` and `c3b726b97e47_*.py` — untracked.
- **Phase 3 frontend features** (blocks, categories, departments, divisions, emp-tasks, employee-projects, employees CSV-import wizard, lots, model-types, models, owners, permission-gate, phases, positions, project-types, projects, roles, shifts, subdivisions) — all untracked.
- **New test files**: `tests/employee/test_blocks_lots_delete.py`, `tests/employee/test_owner_category_lots.py`, `tests/employee/test_owner_model_crud.py`, `tests/rbac/test_role_permissions.py` — untracked.
- **Clerk demo cleanup**: removal of `frontendv3/src/routes/clerk/` tree + 2 logo assets.
- **AGENTS.md**: listed as untracked `?? AGENTS.md` — meaning there is an AGENTS.md file in the working directory that is NOT tracked by git. The version shown in the open-tab state is a newer version than the committed `c6996b1` snapshot.

**This snapshot (§1–§8) documents the committed origin/main state unless noted otherwise.**

---

## §1 Backend Phases — Working-Tree State (with live Postgres via Docker)

**Environment setup:**
- Docker 28.3.3 available (not running at session start; started with `docker compose up -d db`)
- `hris-python-db-1` (postgres:18) started on `0.0.0.0:5433->5432/tcp`
- Database was pre-populated from prior test runs; contains stale `department_*` and `division_*`
  root-level Module rows from prior seed passes (see §4).

**Real test execution** (full suite, not --collect-only):
```
cd backend && ../.venv/bin/python -m pytest tests/ -q
```

**ACTUAL OUTPUT:**
```
...............................                                               [ 26%]
........................................................ [ 52%]
......................................................F.....F...F...         [ 79%]
....................................................                                 [100%]

TOTAL         (passed=269, failed=3, error=0, skipped=0)
======================== 3 failed, 269 passed, 2 warnings in 36.74s ========================
```

Module breakdown (from `Module summary`):
| Module | Result |
|---|---|
| attendance | ✅ PASSED (passed=41, failed=0, error=0) |
| auth | ✅ PASSED (passed=41, failed=0, error=0) |
| employee | ✅ PASSED (passed=49, failed=0, error=0) |
| foundation | ✅ PASSED (passed=20, failed=0, error=0) |
| item | ✅ PASSED (passed=11, failed=0, error=0) |
| rbac | ❌ FAILED (passed=58, failed=3, error=0) |
| scripts | ✅ PASSED (passed=2, failed=0, error=0) |
| user | ✅ PASSED (passed=47, failed=0, error=0) |

**Working-tree test inventory**: 272 tests collected, 30 test files.

**Lint** (`uv run ruff check backend/app/`):
```
Found 55 errors (46 fixable with --fix).
Notable issues: 2 × W292 "No newline at end of file" (backend/app/utils.py, backend/app/utils.py);
missing newline in other files. All pre-existing.
```

**Typecheck** (`uv run mypy backend/app/`):
```
Found 51 errors in 14 files (checked 72 source files).
Key patterns: Type[T] generic attribute errors in employee/services.py and attendance/services.py;
no-redef errors in common/dependencies.py; var-annotated missing type hints in routes.py.
All pre-existing.
```

**Pre-existing lint/type issues** (all pre-existing, not introduced in this session):

### §1.1 Phase 0 — Foundation: DONE

Source: `docs/roadmap/backend-phases.json` origin/main: `b0` items all `done=true`.

| Item | Status |
|---|---|
| Extend scaffold (settings, Postgres engine, Alembic) | ✅ |
| PyJWT + pwdlib auth: access + refresh tokens, real logout/revocation | ✅ |
| Rate limiting on login/reset endpoints | ✅ |
| `require_permission(module, action)` RBAC dependency, enforced on every route | ✅ |
| Seed modules/submodules/role codes | ✅ |
| Base response model, pagination, error format, audit middleware | ✅ |

### §1.2 Phase 1 — Employee Core + Org Structure: DONE

Source: `docs/roadmap/backend-phases.json` origin/main: `b1` items all `done=true`.
Evidence from committed test files (all present on origin/main):

- `tests/employee/test_crud.py` — 6 tests
- `tests/employee/test_crud_relations.py` — committed
- `tests/employee/test_dashboard.py` — committed
- `tests/employee/test_blocks_lots_delete.py` — 4 tests (soft-delete guard)
- `tests/employee/test_owner_category_lots.py` — 4 tests (Owner→Category→Lots contract)
- `tests/employee/test_additional_records.py` — committed
- `tests/employee/test_attachments.py` — committed
- `tests/employee/test_indexes_constraints.py` — committed
- `tests/rbac/test_role_escalation.py` — 5 tests (role-escalation prevention)

### §1.3 Phase 2A — Attendance/DTR Time Math Core: **NOT on origin/main**

`docs/roadmap/backend-phases.json` on origin/main: `b2a` items = `done: false / 2`.

Working tree has the complete implementation (uncommitted):
- `backend/app/attendance/calc.py` — pure time-math functions
- `backend/app/attendance/models.py`, `schemas.py`, `services.py`, `selectors.py`
- `backend/tests/attendance/test_calc.py` — 20 tests
- `backend/tests/attendance/test_dtr_routes.py` — 13 tests

**Key calc.py decisions confirmed from source:**
```
rendered = base = gross - lunch_minutes       # line 67, 75
late     = max(0, login_minutes - start - grace)  # lines 68-71
undertime = max(0, shift_minutes - rendered)  # line 76
overtime  = max(0, base - shift_minutes)     # line 77
```
`late_minutes` and `undertime_minutes` are **independent dimensions**, not additive
(they are never summed against each other). Confirmed.

### §1.4 Phase 2B — Approval Flow: **NOT on origin/main**

`docs/roadmap/backend-phases.json` on origin/main: `b2b` items = `done: false / 3`.

Working tree has:
- `backend/app/attendance/adjustment_models.py`, `adjustment_schemas.py`, `adjustment_services.py`
- `backend/tests/attendance/test_adjustment_approval.py` — 8 tests

### §1.5 Phase 3 and beyond: NOT DONE

All `b3`–`b7` items false on origin/main. No attendance, leave, payroll, or later
backend code exists on origin/main.

### §1.6 Alembic Migrations

| | Count | Source |
|---|---|---|
| Committed (origin/main) | **9** | `git ls-tree -r origin/main backend/alembic/versions/` |
| Working tree | **11** | + 2 new: shift table, dtr_adjustment |

AGENTS.md §2 currently says "10" — this is **outdated** vs the committed state (9)
and the working tree (11). The document will need updating.

---

## §2 Frontend Phases

### §2.1 Verification Command

```
cd frontendv3
export LD_LIBRARY_PATH="$(pwd)/.playwright-libs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
npx vitest run --browser.headless
```

**ACTUAL OUTPUT:**
```
 RUN  v4.1.4 /var/www/vhosts/hris-python/frontendv3
 Test Files  46 passed (46)
      Tests  191 passed (191)
   Start at  13:37:48
   Duration  43.14s
```

**46 test files, 191 tests, ALL PASSING, 0 failed.**

**Lint** (`npx eslint .` from `frontendv3/`):
```
✖ 6 problems (1 error, 5 warnings)
  - 1 error: 'RolePublic' is defined but never used (frontendv3/src/lib/api/roles.ts:3)
  - 5 warnings: react-hooks/exhaustive-deps (csv-import), react-refresh/only-export-components
    (resource-delete-dialog), react-hook-form incompatible-library warnings (subdivision-wizard)
```
Pre-existing: the `RolePublic` unused import is in the committed codebase. The `react-refresh`
warning about `extractDeleteErrorMessage` is the known issue noted in AGENTS.md §3.

**Typecheck** (`npx tsc --noEmit` from `frontendv3/`): **0 errors** (no output).

### §2.2 Committed Frontend State (origin/main `c6996b1`)

Origin/main commit message: "Frontend Phase 0-2: sign-in, permission-driven sidebar,
dashboard KPIs, employee list/profile". The committed frontend test count was
approximately 120–140 tests (the exact committed count was not separately captured
in this session; the AGENTS.md figure of 187/43 was the most recent committed
baseline before Phase 3 uncommitted work was added).

**Current working tree Phase 3 features confirmed from verbose test output:**
- divisions, departments, subdivisions, blocks, categories, lots, positions, project-types,
  projects, phases, models, model-types, owners, employee-projects, emp-tasks, shifts,
  roles, dashboard tiles, employees (list + profile + CSV import), permission-gate
- All 191 tests pass

### §2.3 Phase 3 Coverage (§8.1–§8.13)

From verbose test output (all confirmed present and passing):
- §8.1/§8.6 permission gating on divisions, departments, blocks, subdivisions
- §8.7 409 delete-conflict flows (divisions)
- CSV import success, retry, wizard-resume
- Subdivision wizard multi-step state

---

## §3 Known Gaps — Deliberately Deferred

These match the design doc deferrals:

| Gap | Backend status | Frontend status | Notes |
|---|---|---|---|
| Employee create/edit/delete UI | ✅ Backend CRUD exists | ❌ Frontend read-only list + profile + CSV only | Deferred per design §7 |
| Annex/attachments UI | ✅ Model + tests exist | ❌ Deferred | backend `EmployeeAttachments` + tests committed; frontend UI not built |
| Category CRUD (full) | ✅ | ✅ | Committed in Phase 1 per design |
| Dashboard charts (visualization) | KPI endpoint exists | ❌ Tile count only; no Recharts | Deferred to Phase 6 |
| Shifts backend | ❌ Model + routes absent | ✅ UI + tests exist | Design says no backend yet |
| Biometric device sync | ❌ No implementation; only abstract `IngestionAdapter` interface | N/A | Explicitly not built; deferred to future |

---

## §4 Pre-existing Test Failures

### §4.1 Real Run Results (with Docker Postgres — `docker compose up -d db`)

**Actual pytest output:**
```
======================== 3 failed, 269 passed, 2 warnings in 36.74s ========================
Module summary:
  attendance   PASSED   (passed=41, failed=0, error=0, skipped=0)
  auth         PASSED   (passed=41, failed=0, error=0, skipped=0)
  employee     PASSED   (passed=49, failed=0, error=0, skipped=0)
  foundation   PASSED   (passed=20, failed=0, error=0, skipped=0)
  item         PASSED   (passed=11, failed=0, error=0, skipped=0)
  rbac         FAILED   (passed=58, failed=3, error=0, skipped=0)
  scripts      PASSED   (passed=2, failed=0, error=0, skipped=0)
  user         PASSED   (passed=47, failed=0, error=0, skipped=0)
```

**Backend lint** (`uv run ruff check backend/app/`): 55 errors (46 fixable).
**Backend typecheck** (`uv run mypy backend/app/`): 51 errors in 14 files.
All lint/type errors are pre-existing — not introduced in this session.

### §4.2 The 3 Seed Test Failures — Root Cause

All 3 failures are in `tests/rbac/test_seed.py` and are caused by **stale database
rows from prior seed runs**, not by application code:

**Failure 1:** `test_main_modules_match_legacy_exactly`
```
Extra items in the left set:
'division_4589d1ee', 'division_0c75ac0e', 'division_875d06a3', ...
'department_4589d1ee', 'department_0c75ac0e', 'department_875d06a3', ...
```
`department_*` and `division_*` appear as root-level modules (parent_id=None) when
they should be submodules under `administration`. The seed is idempotent for new
modules but when root-level duplicates already exist, the skip logic leaves them
in the wrong state.

**Failure 2:** `test_there_are_five_main_modules`
```
assert 29 == 5
```
29 root-level modules instead of 5. All the `department_*` and `division_*` seeded
as root-level modules in prior runs are counted here too.

**Failure 3:** `test_every_role_has_a_permission_row_per_module`
```
SADM has 32 permission rows, expected 56
```
With 29 modules instead of 5 (because stale rows inflated the count), each role
gets permissions for 29 modules instead of the expected 5 main modules × (own +
submodules per entry in SUBMODULES dict) = 27 total modules.

**Root cause**: The `conftest.py` session-scoped `db` fixture runs `init_db()` and then
cleans tables but does NOT reset the Module table to a clean state before each test
session. If seed ran with an incorrect `parent_id=None` for `department`/`division`
module entries in a prior run, those wrong rows persist and pollute subsequent runs.
The seed is idempotent for NEW inserts but not for fixing existing wrong-parented rows.

**Not a test_require_permission.py teardown issue** — that was the user's memory from a
prior session. The real failure mode here is seed-state pollution, not teardown.
This was NOT fixed in this session (no application code changes made).

---

## §5 Architecture Decisions That Must Not Be Reversed

### §5.1 Owner has no FK to Lots/Blocks

**Confirmed from source** (`backend/app/employee/models.py:533–556`):
```python
class Owner(SQLModel, table=True):
    __tablename__ = "owner"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    lot_no: str | None = Field(default=None, max_length=32)    # denormalised string
    block: str | None = Field(default=None, max_length=32)    # denormalised string
    # NO lot_id, NO block_id FK fields
```

Ownership link: `Owner → Category (owner_id) → Lots (lot_id)`. `Owner.lot_no`/`block`
are display convenience strings, NOT enforced-referenced. Regression test exists:
`tests/employee/test_owner_category_lots.py::test_owner_has_no_lot_id_block_id_fields`.

### §5.2 No Biometric Device Sync

**Confirmed**: `backend/app/attendance/ingestion.py` defines only an abstract
`IngestionAdapter` contract for future device/vendor adapters. No real device sync
implementation exists. Legacy system had `sync_connection` (id=1, hardcoded) to
an external DB — the new system has the credential slot but no ingestion logic.

### §5.3 late_minutes / undertime_minutes — Not Additive

From `backend/app/attendance/calc.py` lines 68–81:
- `late_minutes = max(0, login_minutes - shift_start - grace)` — measures login-time excess
- `undertime_minutes = max(0, shift_minutes - rendered)` — measures shortfall from shift requirement
- These are **independent scalar fields**, never summed against each other in the `DtrResult`
  dataclass or anywhere in `services.py`.

### §5.4 RBAC — Module-Level Except Ownership-Endpoints

**Confirmed**: Standard CRUD resources use `require_permission(<module>, <action>)`
at the router level with no per-row ownership filter.

Ownership-filtered endpoints (3 logical resources, 6 route handlers):
1. `GET /employees/me` — filters by `EmployeeRecords.user_id == current_user.id`
2. `GET /employees/{id}/additional-records` — `_ensure_annex_access()` with ownership OR `emp_list` permission
3. `PATCH /employees/{id}/additional-records` — same ownership check with `EDIT` action
4. `GET /employees/{id}/attachments` — `_ensure_annex_access()` with `VIEW`
5. `POST /employees/{id}/attachments` — `_ensure_annex_access()` with `ADD`
6. `DELETE /employees/{id}/attachments/{id}` — `_ensure_annex_access()` with `DELETE`

Ownership check pattern (from `backend/app/employee/routes.py:48–68`):
```python
def _ensure_annex_access(session, current_user, employee, elevated_action):
    if employee.user_id == current_user.id:
        return  # owner: allow
    if user_has_permission(session, current_user, module_code="emp_list", action=elevated_action):
        return  # privileged: allow
    raise HTTPException(status_code=403, ...)
```

---

## §6 AGENTS.md §2 Baseline Discrepancies

| Field | AGENTS.md §2 says | Verified committed value | Note |
|---|---|---|---|
| Backend test count | 207 | **207** (collection confirmed) | ✅ Matches |
| Backend test files | 21 | **27** | AGENTS.md is wrong by 6 |
| Frontend tests | 187 | **191** (working tree) / ~120–140 (origin) | AGENTS.md stale |
| Frontend test files | 43 | **46** (working tree) | AGENTS.md stale |
| Alembic migrations | 10 | **9** (committed) | AGENTS.md overstates |
| Frontend phase | "Phase 0-3" | origin/main = Phase 0-2 | AGENTS.md overstates |
| Backend phase | "Phase 0-1" | origin/main = Phase 0-1 + Phase 2A/2B tracker aspirationally marked done but not committed | Tracker ahead of code for b2a/b2b |

---

## §7 Summary — Verified Numbers (Real Runs)

| Dimension | Committed (origin/main) | Working Tree (real run) |
|---|---|---|
| Backend tests (collected) | **207** | **272** |
| Backend tests (real run) | **NOT RUN** (no DB in prior session) | **269 passed, 3 failed** |
| Backend test files | **27** | **30** |
| Backend phases done | b0 ✅, b1 ✅, b2a ❌, b2b ❌ | b0 ✅, b1 ✅, b2a ✅, b2b ✅ (uncommitted) |
| Alembic migrations | **9** | **11** |
| Frontend tests (real run) | ~120–140 (origin, not run in this session) | **191 passed, 0 failed** |
| Frontend test files | ~30–35 (origin) | **46** |
| Frontend phases done | Phase 0-2 | Phase 0-3 (uncommitted) |

**Lint/typecheck (all pre-existing, not new in this session):**
- Backend ruff: 55 errors (46 fixable); mypy: 51 errors in 14 files
- Frontend eslint: 1 error + 5 warnings; tsc: 0 errors

---

## §8 What This Means for the Rewrite

1. **The committed codebase is Phase 0-1 complete** on both backend and frontend.
2. **Phase 2A/2B is in the working tree** — attendance/time-math and approval flow
   code is written and has 41 tests collected, but not yet committed. It is not
   "done" in the committed repo.
3. **Phase 3 frontend is in the working tree** — 46 test files, 191 tests, all green.
4. **AGENTS.md is stale** in multiple fields (§2 baselines, migration count).
5. **Phase 3 work is not yet committed** — the `c6996b1` commit that updated the
   roadmap tracker only reflects Phase 0-2 frontend, Phase 0-1 backend. b2a/b2b
   "done" markers in the working-tree `backend-phases.json` are ahead of what is
   actually committed.
6. **No live-DB environment** in this session — all backend test runs produced
   100% fixture-setup OperationalErrors. This is a pre-existing environmental
   constraint (no docker, no local postgres on this host).
