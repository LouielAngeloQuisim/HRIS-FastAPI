# WCH HRIS — Backend Rewrite Roadmap (Python / FastAPI)

> **Purpose.** This document is the authoritative plan for rebuilding the existing WCH HRIS backend in Python. It is meant to be read **cold, with no access to the original Symfony project** (`F:\laragon\www\wchhris-api`). It captures what the old backend *does* — business logic, data model, workflows, and undocumented edge cases — and prescribes how to rebuild it cleanly.
>
> **Companion deep-dives.** The full schema tables, every route's request/response shape, and every payroll/attendance formula are in the analysis files under `../analysis/` (this repo) or `/tmp/kilo/hris-analysis/`:
> - `01-backend-datamodel.md` — complete Doctrine→SQLAlchemy entity reference (the schema source of truth)
> - `02-backend-payroll.md` — SSS / PhilHealth / Pag-IBIG / BIR math, payslip, 13th-month
> - `03-backend-attendance.md` — DTR pipeline, shifts, overtime, biometric sync
> - `04-backend-leave.md` — leave policies, balances, holidays
> - `05-backend-auth-rbac-misc.md` — auth, RBAC, employee core, org structure, notifications, audit
>
> This roadmap is self-contained for planning decisions; the companion files are the implementation detail.

---

## 0. TL;DR for the implementing agent

- **Keep the logic, throw away the code.** Re-implement every business rule, but in a clean, layered, tested FastAPI app. Do **not** port the Symfony controllers verbatim.
- **Framework:** Python 3.11+, **FastAPI**, **SQLModel** (SQLAlchemy 2.0 + Pydantic), **PostgreSQL**, **Alembic**, **PyJWT** auth, **Pydantic v2** validation. This matches the existing `hris-python` scaffold already in the repo — extend it, don't greenfield it.
- **The 4 risk areas** that must be carried forward *exactly* and locked with parity tests: **(1) payroll calculation**, **(2) government-contribution tables (SSS/PhilHealth/Pag-IBIG/BIR)**, **(3) attendance/DTR time math**, **(4) leave balance ledger**. Everything else is straightforward CRUD.
- **Security is the #1 thing to NOT carry forward.** The original has public mutating endpoints, an unauthenticated password-reset that returns a usable token, privilege-escalation paths, committed secrets, and 0% enforced authorization on most controllers. Build real auth + RBAC from day one.
- **Data types matter.** The original stores all money as MySQL `DOUBLE` (PHP `float`). The rewrite must use `NUMERIC(12,2)` / `Decimal` and pin rounding rules (see §5).
- **Target DB is PostgreSQL**, not MySQL — adjust DDL (no `TINYINT`, use `BOOLEAN`; `DATETIME_MUTABLE` → `TIMESTAMP`; `DATE_MUTABLE` → `DATE`).

---

## 1. What the original backend actually is

| Aspect | Detail |
|---|---|
| Language / framework | PHP 8.2, **Symfony 7.0** |
| ORM | **Doctrine ORM 3.1** (attribute mapping), DBAL 3 |
| API style | JSON REST, ~280 routes across 42 controllers, path prefix `/api` |
| Auth | **Lexik JWT** (RS256), 24h token, no refresh, no logout/revocation |
| DB | MySQL/MariaDB (single connection). A *second* runtime PDO connection reads a biometric-device DB. |
| Cache | APCu metadata/query/result + Doctrine 2nd-level cache (configured but unused) |
| Pagination | KnpPaginatorBundle |
| CORS | nelmio/cors-bundle |
| Email | Symfony Mailer (GMail SMTP) |
| Notable | No console commands, no queues/cron workers, no message bus. Long-running work is synchronous HTTP. |

**Module map (controllers → domain):**
Employee & HR core, Payroll, Government contributions (SSS/PhilHealth/Pag-IBIG/BIR), Attendance/DTR/Shifts, Leave, Projects/Manpower/Construction, Auth/RBAC, Notifications/Audit/Sync, SuperAdmin/Permission (mostly stubs).

---

## 2. Target architecture (recommended)

Reuse the existing `hris-python/backend` scaffold. It already provides the right bones: router-per-resource, `app/config` (settings + db), `app/user` (auth), `app/item` (example resource with models/schemas/routes/services/selectors), `app/common` (paginators, security, dependencies), Alembic, and a `tests/` harness.

### 2.1 Layered structure (per resource)
```
app/
  config/            settings.py (env), database.py (engine/session)
  common/            security.py (JWT, pwdlib), dependencies.py (get_db, get_current_user), paginators.py
  auth/              routes (login, refresh, logout, password-reset), deps, services
  employee/          models.py, schemas.py, routes.py, services.py, selectors.py
  payroll/           ... (payroll, payslip, payroll_profile, payroll_groups)
  gov_contrib/       ... (sss, philhealth, pagibig, bir config + loan logic)
  attendance/        ... (dtr, shifts, overtime, sync)
  leave/             ... (leave_request, leave_policy, balances, holidays)
  org/               ... (department, division, project, blocks, model, owner, category)
  rbac/              ... (user, user_type, modules, permissions)
  notifications/     ... (notifications, audit)
```
- **models.py** = SQLModel table entities.
- **schemas.py** = Pydantic request/response DTOs (separate Create/Read/Update).
- **routes.py** = thin FastAPI routers; delegate to services.
- **services.py** = business logic, transactions (`async with db.begin()`), queries.
- **selectors.py** = read-only query helpers (optional, like the repo pattern).

### 2.2 Cross-cutting
- **Auth:** PyJWT access tokens (15–60 min) + refresh tokens (httpOnly cookie or rotation). Argon2 via `pwdlib` (already in scaffold). Real password policy + rate limiting on login/reset.
- **RBAC:** first-class. `user_type` → `role` → `permissions` (scoped to module + action). A `require_permission(module, action)` dependency. **Enforced on every route** (the original did not).
- **Validation:** Pydantic v2 at the boundary; domain invariants inside services.
- **Transactions:** every write wrapped in a DB transaction; the original had none.
- **Money:** `Decimal` + `NUMERIC(12,2)` everywhere; a single `round_money()` helper.
- **Time:** store UTC `TIMESTAMP`/`DATE`; accept/emit ISO-8601; keep the original's `Y-m-d`/`H:i:s` semantics by converting at the boundary.
- **Observability:** structured logging, an audit-trail write path that is actually read, request-id propagation.

### 2.3 Why FastAPI + SQLModel (not Django)
Matches the existing repo investment, gives OpenAPI for the frontend codegen (`@hey-api/openapi-ts`), async-friendly, and keeps the same layered discipline the scaffold already enforces. Django would be fine too but would mean discarding the scaffold.

---

## 3. What MUST be replicated (functional scope)

### 3.1 Employee & HR core
- `EmployeeRecords` master record: employee number (`EMP####`), personal, contact, employment, position, department/division, shift, payroll-profile links. Soft-delete via `employee_status`/`is_deleted`.
- `EmployeeAdditionalRecords` PII annex. `EmployeeAttachments` (files).
- CRUD for Department, Division, Subdivision, Position (model types), and the **construction/manpower domain** (Project, Phase, Blocks, Lots, Model, ModelTypes, Owner, Category, EmployeeProjects, EmpTask). These are core to this business — do not treat as optional.

### 3.2 Payroll (highest-risk)
- Per-employee payroll generation for a cutoff/period:
  - `renderedMinutes` from attendance minus approved overtime minutes → `renderedDays = round(minutes/480, 2)`.
  - Gross (taxable + non-tax) from `dailyRate * renderedDays + allowance/2 + approvedOT*overtimeRate − undertime*lateRate + taxable adjustments`.
  - Mandatory dues (SSS/PhilHealth/Pag-IBIG) **halved** for semi-monthly; loans **not** halved.
  - `net = round(gross_non_tax − (mandatory + tax + loans), 2)`.
  - 13th-month component = enabled parts of `dailyRate*renderedDays + salary_adjustment + tax_shield`.
- Payslip + Year-To-Date view.
- Payroll groups (cutoff windows) and date-range lookup.
- **CRITICAL BUG TO DECIDE ON (see §5):** the original's preview/profile endpoint computes dues/tax **without** the `/2` halving, so preview ≠ generation. The rewrite should make preview and generation share one calculation function.
- No Excel/CSV export exists — if wanted, add deliberately (original was JSON-only).

### 3.3 Government contributions (highest-risk)
- **SSS:** bracket scan on `basic_salary = monthly + allowance` → `contributionTotalEe`. Port the full bracket table + employer share + EC/MPF if present.
- **PhilHealth:** `min(salary, maxCap) * employeeShare/100` (floor at `minCap`).
- **Pag-IBIG:** `min(salary, cap) * share/100`, else `salary*0.01` if ≤1500 (tiered cap).
- **BIR withholding tax:** `TaxConfig` is treated as **annual** — generation halves both bracket bounds and base per cutoff; returns 0 if no bracket matches. Port the full bracket table + exemptions + tax-shield (de minimis) handling.
- **Loan amortization:** SSS loans, Pag-IBIG loans, cash advances — per-period deduction amounts, balance decrement, history rows (`*LoansHistory`, `CashAdvanceHistory`, `LoanHistory`). Port exactly; watch the `deductLoans` HDMF remark bug in the original (stale `$remark` misclassifies HDMF loans) — fix it.
- Config CRUD screens for each agency table.

### 3.4 Attendance / DTR / Shifts / Overtime (highest-risk)
- **Biometric sync:** a second DB connection (`SyncConnection` rows hold credentials) copies `worker`/`worker_logs` from the device DB. Port the sync endpoint + pairing logic.
- **DTR pipeline:** raw punches are assumed *pre-paired* IN/OUT by the device. `rendered = diffMinutes(login,logout) − 60` (hardcoded lunch — **flag**, see §5); `overtime = max(0, rendered − shiftMin)`; `undertime = max(0, shiftMin − rendered)`, `shiftMin = shift.total_hours_minus_lunch ?? 480`.
- **Absence detection:** per scheduled weekday with no login in a semi-monthly cutoff → an "Absent" 0/0/0 row.
- **Shifts:** start/end/lunch/days_of_week/total_hours_minus_lunch; assigned to a User.
- **Overtime:** stored in minutes; **only `overtime_approved` is paid**. Single-level approval, no role gate in original (add one). No min threshold, no rest-day/holiday rate in original.
- **Night differential:** **NOT implemented** in the original — do not invent it unless product wants it.
- **DTR adjustments:** carry an OT log into the next cutoff; original sums into pay *without* approval (inconsistent) — fix.

### 3.5 Leave & Holidays
- **Leave types = rows in `leave_policy`** (no enum, no paid/unpaid flag — all paid by omission). Port `LeavePolicy`, `YearlyEmployeeLeave` (per-employee/year header), `SelectedEmployeeLeaves` (the real balance ledger), `EmployeeLeaves` (a façade controller, **not an entity**).
- **Balances:** annual grant copied once from `LeavePolicy.days`. **No monthly accrual, no carry-over logic, no credit-on-reversal.** Debit-on-approval. Port as-is, but design the ledger so accrual/carry-over can be added later.
- **Approval:** status 0 Pending / 1 Approved / 2 Rejected (2 only inferred in original). Single-step, no role gate (add one).
- **Holidays:** `HolidayConfig` (template) + `YearlyHoliday` (dated instances). **Regular vs special non-working is NOT modelled**; multipliers are write-only; **holiday pay is not implemented** and **nothing answers "is date X a holiday?"**. Port the data model; decide explicitly whether to implement holiday pay (recommended: implement the date check + rest-day/holiday OT since payroll currently ignores it — this is a known gap, not a required carry-forward).

### 3.6 Auth / RBAC / Notifications / Audit
- Login via `identifier` (email **or** username **or** contact_no) + password. JWT. Reset via emailed signed token (NOT a token returned in the response body).
- RBAC: `UserType` (role, `user_code` e.g. `SUR`) → modules (`MainModules` 5 top-level) → `SubModules` (24 sets) with `can_view/can_add/can_edit/can_delete`. Port these 24 submodule definitions as seed data. Enforce via dependency.
- Notifications (in-app + email). Audit trail (write **and** read path; do not log plaintext passwords).
- Dashboard KPIs (9 metrics) — port the computation.

### 3.7 Things explicitly OUT of scope (do not port)
- The biometric device's own schema is external; only the sync reader + `worker`/`worker_logs` local mirrors are in scope.
- Dead entities: `Options`, `ProjectType`, `ThirteenthMonthPayConfig` (0 controller refs). Confirm before dropping.
- The committed `public/excel_files/empfiles.csv` (182 employees) — import via a proper seed/migration, not a web-root CSV.

---

## 4. Data model & migration plan

> Full field/relationship tables: `01-backend-datamodel.md`. The original has **no `#[ORM\Table]`**, so every table name is machine-derived by Doctrine's `underscore_number_aware` strategy from the class short name. Because there are no digits in any class, the rule reduces to: insert `_` before an uppercase letter preceded by a lowercase letter/digit, then lowercase. **Runs of capitals are NOT split.**

**Important table-name examples (carry these exact names or provide a mapping):**
| Original class | Original table |
|---|---|
| `EmployeeRecords` | `employee_records` |
| `DTRAdjutments` | `d_t_r_adjutments` (note the class typo) |
| `SSSConfig` | `s_s_s_config` |
| `PagibigLoansHistory` | `pagibig_loans_history` |
| `EmployeePayrollProfile` | `employee_payroll_profile` |

**Recommendation:** in the rewrite, use **clean, intentional table names** (snake_case, singular, no `d_t_r_` artifact) and either (a) build the new schema fresh and migrate data by column mapping, or (b) keep the ugly names for 1:1 parity. Prefer (a) with a documented mapping table in the migration scripts — cleaner long-term, and the business logic doesn't care about table names.

**DB engine change (MySQL → PostgreSQL):**
- `TINYINT(1)` → `BOOLEAN`.
- `DATETIME_MUTABLE` → `TIMESTAMP` (store UTC).
- `DATE_MUTABLE` → `DATE`.
- `DOUBLE` (money) → `NUMERIC(12,2)` / `Decimal`.
- `Types::ARRAY` (stored as serialized arrays, e.g. SubModule flags) → native `JSONB` or a proper related table.
- Add missing FKs / indexes the original lacked (see §5).

**Migration strategy:**
1. Stand up the new Postgres schema via Alembic (fresh, clean names).
2. Write an **ETL script** (`scripts/migrate_wch.py`) that connects to the legacy MySQL DB (read-only) and copies rows with an explicit column/name mapping. Run in a transaction per table; log skips.
3. Backfill derived data (e.g. leave balances, audit) as needed.
4. **Parity test:** for a sample of employees, regenerate one payroll cutoff in both systems and diff net pay to ≤0.01. Gate the cutover on this passing.

---

## 5. Known weak spots / hacks — DO NOT CARRY FORWARD (register)

> Full list with file:line: `02/03/04/05-*.md` "Bugs / Weak Spots" sections.

**Security (blockers):**
- Public, unauthenticated, **mutating** endpoints (`/sync/worker`, `/check/emp/dtr`, `/salary/*`, `/tax_shield*`).
- Password reset returns the token in the **response body**; `resetPassword()` never checks expiry; token is a usable JWT. → Implement email-sent, signed, expiring reset tokens.
- `signup` outside the `^/api` firewall → anonymous account creation with caller-chosen role. → Gate behind admin or remove.
- `revalidate-session` mints a JWT for any `user_id`. → Remove / strongly authenticate.
- Privilege escalation: `UsersController::updateUser()` can set role; `SuperAdminController` has no super-admin check; RBAC `updateMainModules` swaps two args. → Real role enforcement.
- **Secrets committed** to `.env` (Gmail app password, JWT passphrase, prod creds). → Use a secret store / untracked env.
- **Employee PII CSV in the public web root.** → Never.
- **Plaintext passwords in the audit table** (logs raw request bodies). → Redact.
- ~13.6% of routes call `validateUserAccess`; 15 controllers inject it but never call it. → Enforce centrally.

**Correctness (must fix or consciously preserve):**
- **Money as `float`/`DOUBLE`** everywhere → rounding drift. → `Decimal`.
- **Preview ≠ generation** (no `/2` halving in preview). → Single shared calc.
- Hardcoded **`−60` lunch** ignores `lunch_break_duration`. Decide and document.
- `saveEmployeePayrollProfile` zeroes all loan balances unless loan arrays resent. → Idempotent updates.
- `/api/all-employee-payroll` hardcodes `2023-10-01/15`. → Parameterize.
- `deductLoans` Pag-IBIG remark bug misclassifies HDMF loans. → Fix.
- Double-approval re-debits leave balances; `updated_by` client-supplied (self-approval). → Server-authoritative actor.
- Route-name collisions drop endpoints (`/api/gov-dues` vs `/api/gov-total-dues`; `updateList()` 500s). → Unique, tested routes.
- No DB transactions anywhere → partial writes. → Wrap writes.
- N+1 loops, raw SQL without parameterization in places (sync PDO is correctly bound — keep that pattern). → Use ORM / parameterized SQL.

---

## 6. Phased milestones

**Phase 0 — Foundation (1–2 wks)**
- Extend the `hris-python/backend` scaffold. Settings, Postgres engine, Alembic, PyJWT + pwdlib auth, `get_current_user`, refresh/logout, rate limiting.
- Real RBAC dependency + seed the 5 modules / 24 submodules / role codes.
- Base `ResponseModel`, pagination, error format, audit middleware.

**Phase 1 — Employee core + Org structure (2 wks)**
- `EmployeeRecords` (+ additional records, attachments), Department, Division, Subdivision, Position, and the construction/manpower domain (Project, Phase, Blocks, Lots, Model, ModelTypes, Owner, Category, EmployeeProjects, EmpTask).
- Users/UserType CRUD with enforced RBAC. Dashboard KPIs.

**Phase 2 — Attendance / DTR / Shifts / Overtime (2–3 wks)** ⚠ high risk
- Entities + sync reader (parameterized PDO/SQLAlchemy equivalent to the device DB).
- Rendered/late/undertime/absence math **with shared constants module**; overtime approval with role gate; DTR adjustments with approval.
- Parity tests vs legacy outputs.

**Phase 3 — Leave & Holidays (1–2 wks)**
- `LeavePolicy`, `YearlyEmployeeLeave`, `SelectedEmployeeLeaves` ledger; request lifecycle + approval; holidays (implement the date-check + decide on holiday pay).

**Phase 4 — Payroll & Government contributions (3–4 wks)** ⚠ highest risk
- SSS/PhilHealth/Pag-IBIG/BIR tables + calculators (single source of truth, used by both preview and generation).
- Loan amortization (fix HDMF remark bug). Payroll generation (per-employee + bulk), payslip/YTD, payroll groups.
- 13th-month. **Parity tests against legacy payroll are the gate.**

**Phase 5 — Notifications, Audit, Reports, Polish (1–2 wks)**
- In-app + email notifications (no hardcoded inbox). Readable audit trail. Any reports.

**Phase 6 — Data migration & cutover (1–2 wks)**
- ETL from legacy MySQL → new Postgres (mapping script). Parity payroll diff. Soft launch, dual-run, then cutover.

**Phase 7 — Hardening**
- Pen-test the auth/RBAC fixes; load test payroll generation; backup/restore; remove legacy system.

---

## 7. Open decisions the implementing agent must confirm with the product owner

1. Keep ugly legacy table names (1:1 parity) vs clean names + mapping ETL. **(Recommend clean + mapping.)**
2. Holiday pay + rest-day/holiday OT: implement now (closes a gap) or stay faithful to "not implemented"?
3. Leave: keep no-accrual/no-carry-over behavior, or modernize the ledger while preserving current balances?
4. Payroll frequency: original hard-codes semi-monthly. Make configurable (weekly/monthly/semi-monthly)?
5. Preview-vs-generation discrepancy: unify on the *generation* (halved) semantics?
6. Lunch deduction: keep hardcoded 60 min or use `lunch_break_duration`?
7. Biometric device: same vendor/DB in the new environment, or replace the sync with file/API import?

---

## 8. Success criteria

- New API covers 100% of the **live** original endpoints (filter out dead routes).
- Payroll net pay matches legacy to ≤₱0.01 on a representative sample (parity test in CI).
- Auth + RBAC enforced on every route (automated test that a low-privilege user cannot hit admin endpoints).
- All money in `Decimal`; no secrets in VCS; no PII in web root; no public mutating endpoints.
- OpenAPI spec generated; frontend `frontendv3` consumes it via codegen.
