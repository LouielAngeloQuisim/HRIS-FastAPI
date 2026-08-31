# 08 — Rewrite Plan: Python Backend + `frontendv3` (React)

**Purpose:** Consolidate the read-only analyses of the two reference projects into a concrete
rewrite plan for the target `hris-python` scaffold.

- **Reference backend API:** `/mnt/f/laragon/www/wchhris-api` — Symfony 7 / PHP 8.2 / Doctrine ORM 3.1 / Lexik JWT. Analyzed in `01`–`05`.
- **Reference frontend:** `/mnt/f/laragon/www/wchhris` — Symfony 6 / Twig server-rendered on the Tailwick v1.1.0 theme. Analyzed in `06`–`07`.
- **Target scaffold:** `/var/www/vhosts/hris-python` — FastAPI + SQLModel backend, React 19 + Vite + TanStack (Router/Query/Table) + shadcn/ui + Tailwind 4 + openapi-ts frontend. See `AGENTS.md`.

This document is the **action plan**. The `0N-*.md` docs are the evidence base and are cited by section.

---

## 1. Target scaffold — current state

The `hris-python` scaffold is operational infrastructure only:

- Backend: FastAPI app factory, SQLModel engine, Alembic (5 migrations), JWT auth, `User`/`Item` stub models, CRUD/deps/router conventions per `AGENTS.md`.
- Frontend: TanStack Router/Query/Table, shadcn/ui, Tailwind 4, dark-mode `ThemeProvider`, auto-generated `src/client/` via openapi-ts. **No HRIS domain code yet** — only auth flows, a placeholder dashboard, and generic Items/Users admin pages.

So the rewrite **extends** this scaffold rather than starting greenfield. Key alignment points already satisfied:

- Router-per-resource + `crud.py` + `deps.py` (`SessionDep`/`CurrentUser`) matches the analysis recommendation in `01 §1`.
- SQLModel (SQLAlchemy under the hood) makes the Doctrine→SQLAlchemy port mechanical (`01 §1.7` type crib sheet).
- openapi-ts client generation means the frontend consumes the same contract the API publishes (`06`).

---

## 2. Port scope — keep / drop

| Keep (port) | Drop (do NOT port) |
|---|---|
| All **live** entities & business logic (`01 §3`, `02`–`04`) | **149 / 151** dead root templates, customizer, cart drawer (`07 §6`) |
| The 24 live sidebar routes + their pages (`07 §2.6`, `04 §4`) | The 3 Symfony maker stubs + 3 controllers that render **missing** templates (`07 §4.12`, `06`) |
| Permission class-name hiding pattern → port as RBAC gating (`07 §3.13`, `05 §3g`) | Native HTML5-only validation → replace with `react-hook-form` + `zod` (`07 §3.3`) |
| Government-contribution math (SSS/Pag-IBIG/PhilHealth/BIR) (`02`) | Un-localised Indian-payroll demo content in payslip pages (`07 §4.8`) |
| `Public Sans` font, `custom-500 #3b82f6` brand, `zink-*` dark ramp, `.card` canon (`07 §1`) | Tailwick `data-modal-target` + Encore stub → replaced by shadcn + Vite (`07 §5`) |

Dead entities already identified in the API (`01 §6`): lookup tables with zero consumers, write-only audit features, etc. Skip them in the port.

---

## 3. Backend rewrite plan (FastAPI / SQLModel)

### 3.1 Entity port sequence (dependency-ordered phases)

Follow `01 §3` domain grouping. Recommended build order (each phase = one Alembic migration batch):

1. **Auth / RBAC** (`01 §3g`, `05 §3`): `User` (exists), `UserType`/`Role`/`Permission` + `can_*` flags. Port Lexik-JWT → PyJWT access tokens already present; add role/permission checks in `deps.py`.
2. **Org structure** (`01 §3a`): `Division` → `Department` → `Subdivision` → `Phase` → `Project` (self-referential divisions, FKs to `EmployeeRecords`).
3. **Employee core** (`01 §3a`): `EmployeeRecords` (master, demographic enums `01 §4.4`), `Worker` (construction manpower), `AccountabilityRecords`, document types.
4. **Attendance / DTR / Shifts** (`01 §3d`, `03`): `AttendanceTypes`, `Shift`/`ShiftAssignment`, `Dtr` + `DtrAdjustment`, `OvertimeRequest`, `TimeLog` (biometric sync).
5. **Leave / Holiday** (`01 §3e`, `04`): `LeavePolicy`, `LeaveType`, `SelectedEmployeeLeaves` (request), `LeaveBalance`, `HolidayConfig`/`HolidayInstance`.
6. **Payroll** (`01 §3b/3c`, `02`): `PayrollPeriod`, `PayrollGroup`, `EmployeePayrollProfile`, `Payslip`/`PayslipLine`, `SssConfig`/`PagibigConfig`/`PhilHealthConfig`/`BirTaxConfig` (bracket tables), `Loan`/`Advance`, `PayrollReport`.

### 3.2 API surface per module

Mirror the Symfony controller routes (`05` controller inventory) as FastAPI routers under `app/api/routes/`:

- `auth.py` (login/refresh/test-token — exists), extend with role/permission introspection.
- `employees.py`, `org.py` (divisions/departments/…/projects), `attendance.py` (DTR, shifts, overtime, sync), `leave.py` (policies, requests, balances, calendar, holidays), `payroll.py` (periods, groups, generate, payslip, reports, gov-config).
- Register each in `app/api/main.py` (`AGENTS.md` convention). Return SQLModel/Pydantic DTOs; owner-scoping + superuser guards already established.

### 3.3 Auth / RBAC port

- Replace the `is_superuser` boolean-only model (`AGENTS.md` gap #8) with the reference `UserType` + role/permission matrix (`05 §3g`, `01 §4.8`). Implement `require_permission("can_view_division")` dependency.
- Permission flags are booleans on the role — straightforward SQLModel columns.

### 3.4 Business-logic ports (highest-risk, port verbatim then test)

- **Payroll math** (`02`): SSS/Pag-IBIG/PhilHealth bracket lookups, BIR tax tables, semi-monthly frequency (hard-coded in ref — make it a `PayrollGroup` column, `01 §4.13`), loans/advances, 13th-month, payslip line aggregation. Port as pure functions in `app/.../payroll/` with unit tests mirroring the Symfony service outputs.
- **Attendance/overtime** (`03`): shift-vs-DTR diffing, overtime approval flow (status 0/1/2, `01 §4.1`), DTR adjustment, time-log sync idempotency.
- **Leave balances** (`04`): policy eligibility enums (`01 §4.3`), accrual, request lifecycle.

### 3.5 Conventions

Adhere to `AGENTS.md`: one router file per resource, explicit `crud.py` functions (no generic repo), SQLModel `table=True` entities + separate create/update/public DTOs, Alembic for every schema change, 90% coverage threshold (payroll/attendance/leave logic especially).

---

## 4. Frontend rewrite plan (`frontendv3`)

### 4.1 Design tokens → Tailwind 4 config

From `07 §1` (reverse-engineered since no `tailwind.config.js` exists in ref):

- Brand: `--color-custom-500: #3b82f6`, hover `#2563eb`.
- Dark surfaces: `zink-700 #132337` (cards), `zink-800 #0f1824` (page), `zink-600` borders. Light: `body-bg #f1f5f9`, card border `#e2e8f0`.
- Font: **Public Sans** (200–700) via `@fontsource` (ref used Google Fonts CDN — self-host for offline).
- `.card` canon: `rounded-md border border-[#e2e8f0] p-5` (light) / `border-zink-600` (dark).
- Icons: **lucide-react** (shadcn default) + `remixicon` package to match ref icon set.

Define these as CSS variables in `src/index.css` and map to Tailwind theme tokens so dark mode (already wired via `ThemeProvider`) flips automatically — replacing the ref's 3 `data-*` attribute + `sessionStorage` hack (`07 §2.2`).

### 4.2 App shell

- **Sidebar** (`07 §2.6`): rebuild the **live** 24-route tree as a shadcn `Sidebar` + collapsible groups, driven by a typed nav config; gate items by permission (`07 §3.13`). Drop the 866 KB / 1 080-line static `_sidebar.html.twig`.
- **Topbar** (`07 §2.4`): search, notification bell (port `_notification-area` as a React query + Sonner/sheet), user menu. Remove the dead cart drawer.
- **Active route**: TanStack Router `useLocation`/`Link` active state replaces the ref's exact `location.pathname` string match (`07 §2.6`).
- **Chromeless layout** for auth pages → port `without-nav.html.twig` as a `login`-style route tree (`07 §4.1`).

### 4.3 Routing map (24 live routes → TanStack routes)

Grouped exactly as the live sidebar (`07 §2.6`, `04 §4`):

| Group | Routes (port) |
|---|---|
| Dashboard | `dashboard` |
| Projects | `project` (Project Management module) |
| Human Resource | `app_employee` (employees), `app_attendance` (DTR) |
| Administration | `division`, `department`, `subdivision`, `phase`, `view_owner`, `view_models`, `adm_model_types`, `adm_user_settings`, `adm_shifts` |
| Super Admin | `super_roles`, `super_sync` |
| Payroll Admin | `app_sss_config`, `app_pagibig_config`, `app_bir_config`, `app_phil_health_config`, `view_employee_payroll`, `app_payroll_reports` |
| Leave Admin | `app_overtime_request`, `app_leave_policy`, `app_employee_leaves`, `app_holiday`, `app_leave_request`, `app_leave_calendar` |

Create one route file per group; nested CRUD pages as sub-routes. Do **not** create routes for the 4 missing/maker-stub templates (`07 §4.12`).

### 4.4 Component-pattern substitutions

| Reference (Twig) | `frontendv3` replacement |
|---|---|
| List.js + List.Pagination (`07 §3.1`, 28 pages) | **TanStack Table** + React Query pagination (already in stack) |
| Tailwick `data-modal-target` per-row modals (`07 §3.2`) | **shadcn `Dialog`/`Sheet`**, one instance per page (fix the per-row duplication antipattern) |
| Choices.js selects (`07 §3.4`) | shadcn `Select` / `Command` combobox |
| Flatpickr (`07 §3.5`) | `react-day-picker` (shadcn `DatePicker`) |
| FullCalendar (`07 §3.6`) | `react-big-calendar` or keep FullCalendar React wrapper for leave calendar |
| Toastify (`07 §3.10`) | **Sonner** (already in stack) |
| Dropzone (`07 §3.12`) | shadcn file-upload + `uppy`/native fetch |
| Native HTML5 validation | `react-hook-form` + `zodResolver` |
| `permission.js` class hiding (`07 §3.13`) | RBAC hook `useCan('can_edit_division')` → conditionally render |

Drop unused libs (`07 §3.0`): Grid.js, Select2, ApexCharts (except 1 chart page), SweetAlert2 (use Sonner/Dialog), Morris, etc.

### 4.5 Page build order

1. Auth (login, recover, reset) — chromeless.
2. App shell (sidebar/topbar/layout/theme).
3. Org structure + Administration CRUD (simplest, no heavy logic).
4. Employee master + profile (largest form surface).
5. Attendance/DTR + overtime.
6. Leave (policy/request/balance/calendar/holiday).
7. Payroll (config → period → generate → payslip → reports).
8. Dashboard KPIs (replace stub `07` index).

### 4.6 API client

Regenerate `src/client/` with openapi-ts after each backend router is added (`AGENTS.md`). Frontend already has the global 401 handler and `useAuth` — extend with permission claims.

### 4.7 Build / styling replication

- Kill the ref's dual broken pipeline (`07 §5`): no Encore, no committed 660 KB `tailwind2.css`. Use the existing Vite + Tailwind 4 + `@tailwindcss/vite` from the scaffold.
- Port only the **used** SCSS partials (`07 §5.1`): `tailwind.scss` tokens, `fonts.scss`, `icons.scss`. Skip `plugins/_gridjs.scss` (Grid.js unused).

---

## 5. Cross-cutting

- **Data migration:** snapshot the MySQL `wchhris-api` DB; ETL into Postgres per the entity map (`01 §2` migration history + drift notes). Prioritise `EmployeeRecords` + payroll history.
- **API compatibility:** greenfield FastAPI contract (not byte-compatible with Lexik JWT). Frontend is rebuilt anyway, so no need to mimic Symfony route paths.
- **Calendar/report libs:** decide `react-big-calendar` vs FullCalendar React; PDF payslips need a generator (e.g., `@react-pdf/renderer` or server-side WeasyPrint) — open decision.
- **Government tables data:** SSS/Pag-IBIG/PhilHealth/BIR brackets must be sourced/verified for current-year rates before payroll port (`02`).

---

## 6. Phased rollout roadmap

| Phase | Backend | Frontend | Exit criterion |
|---|---|---|---|
| 0 | Scaffold confirm, token config | Token config, theme | Dev env runs |
| 1 | Auth/RBAC + org structure (`3.1.1-2`) | Auth pages + shell | Login + admin CRUD |
| 2 | Employee core (`3.1.3`) | Employee master/profile | Employee CRUD + search |
| 3 | Attendance/DTR/overtime (`3.1.4`) | DTR + overtime UI | DTR view + OT request |
| 4 | Leave/holiday (`3.1.5`) | Leave + calendar | Leave request/approval |
| 5 | Payroll + gov-config (`3.1.6`) | Payroll + reports | Payslip generation matches ref |
| 6 | Data migration + dashboard | Dashboard KPIs | Production cutover |

---

## 7. Risks & open decisions

- **Payroll correctness** is the top risk — port `02` math with parity tests against the Symfony outputs before trusting.
- **RBAC model** must replace `is_superuser`-only (`AGENTS.md` gap #8) early; retrofitting later is costly.
- **Calendar/report library** choice (§5) — confirm before Phase 4/5.
- **Dead entities** (`01 §6`) must be excluded or they bloat the schema.
- **Ref bugs to not replicate:** 3 missing-template controllers, broken `_page-wrapper` div balance, sessionStorage-only theme, per-row modal duplication (`07 §6.3`).

---

## 8. Effort estimate (relative)

Backend: ~6 domains x (models + crud + router + tests). Frontend: ~24 routes x (page + table + dialogs). Payroll/attendance/leave logic = the bulk of risk. Treat Phases 1-2 as an MVP slice; 3-5 as iterative increments; 6 as migration.
