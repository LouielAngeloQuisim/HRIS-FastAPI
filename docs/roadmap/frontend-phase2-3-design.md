# Frontend Phase 2–3 Design (frontendv3)

> **PLANNING-ONLY document.** No implementation code is written in this task. This
> produces the design for review/approval before any frontend source changes.
>
> Scope: remainder of **Phase 2** (Division / Department / Shifts / Employee Settings
> CRUD + CSV import — employee create/edit/delete & CSV were *deferred*, not built)
> and all of **Phase 3** (Subdivisions / Phase / Owner / Models / ModelTypes,
> Employee Projects / Manpower / Subdivision Wizard, RBAC Roles & Access editor).
>
> Backend CRUD for every resource in this pass already exists and is tested
> (backend Phase 1, `b1`), per `docs/roadmap/phase1-design.md`. Frontend only
> consumes those contracts — it does not redefine them.
>
> **Authoritative location note:** This agent's write permission only allows plan
> files under `.kilo/plans/`, `.plans/`, `.opencode/plans/`, or `plans/`. The
> originally-requested `docs/roadmap/frontend-phase2-3-design.md` path is blocked by
> the permission ruleset, so the canonical copy lives here at
> `.kilo/plans/frontend-phase2-3-design.md`. Move/copy it to `docs/roadmap/` once
> permissions allow (no content change needed — the body is identical to what would
> be at the requested path). This is the corrected, OQ-verified version.

---

## 0. Canonical pattern references (do NOT reinvent these)

The following are the established, tested conventions in `frontendv3`. Every new
resource in this pass must reuse them; divergence is allowed **only** where a
resource's shape genuinely requires it (see §5 for the explicit extraction list).

| Concern | Reuse this | Notes |
|---|---|---|
| List + table + toolbar + pagination + URL state | `features/employees/*` (server-paged via `useEmployees`) **or** `features/tasks/*` (client-paged via local `tasks` data) | Employees = server data (real API). Tasks = static demo data. New real resources follow the **employees** model: `useQuery` + `keepPreviousData`, page/pageSize in URL search, `useTableUrlState`. |
| Row-level actions ("..." menu) | `features/tasks/components/data-table-row-actions.tsx` | Dropdown with Edit / Delete (delete as `DropdownMenuShortcut`). Use when >2 actions. |
| Bulk select + bulk actions | `components/data-table/bulk-actions.tsx` + `features/tasks/components/data-table-bulk-actions.tsx` | Floating toolbar, a11y live region, Escape-to-clear. |
| Create/Edit form | `features/tasks/components/tasks-mutate-drawer.tsx` | **Side `Sheet` drawer** with `Form` + `react-hook-form` + `zodResolver`, `SheetFooter` Save/Close. |
| Confirm-before-destroy | `components/confirm-dialog.tsx` (wraps Radix `AlertDialog`) | Standard delete confirmation. `users-delete-dialog.tsx` shows typed-confirm variant + `Alert` warning. |
| Permission gating | `context/permissions-provider.tsx` → `useCan(module, action)` | Deny-by-default; superuser bypass. Employees gates `canView` at page entry. |
| Dialog state machine | `hooks/use-dialog-state.tsx` + a `*-provider.tsx` context (see `tasks-provider.tsx`) | One context holds `open` + `currentRow`; `*-dialogs.tsx` renders all drawers/dialogs. |
| CSV import shell | `features/tasks/components/tasks-import-dialog.tsx` | File-input-only stub today — **must be replaced** with the real flow in §3. |
| Error envelope | `lib/api/types.ts` → `ErrorResponse` / `ErrorBody` | `{ success, detail, error:{type,message,details[]}, request_id }`. 409 conflicts carry a machine-readable `error`. |
| Sidebar nav | `components/layout/data/sidebar-data.ts` | Each item already has a `permission:{module}` gate and an `url`. |

**Key reuse rules (per the design brief):**
- Column alignment: text → left, numbers/dates → right (use `meta.thClassName`/`tdClassName` + `text-right`).
- Empty / loading / error states must be consistent across **every** resource. Reuse the `isPending` / `isError` / Try-again pattern just added to Employees (`features/employees/index.tsx` lines 45–67). Any new list page that hits the API **must** include the same three states.
- No optimistic UI for resources with backend guard logic (Division / Blocks / Lots 409 checks). Wait for server confirmation, then invalidate/refetch.
- Every create/edit/delete control checks `useCan(...)` before rendering (mirror `EmployeesAuthGate` + `useCan('emp_list','view')`).

---

## 1. Resource-by-resource plan

Module/action pairs are taken verbatim from `phase1-design.md §2`. All list
endpoints filter `is_deleted = false` server-side; the frontend just renders what
it gets.

### 1.1 Division — module `division`
- **Fields:** `code` (unique, required), `name` (required), `description`, `director_id` (FK → Employee, nullable).
- **List columns:** Code | Name | Description | Director (id slice/name) | Created | actions.
- **Create/Edit pattern:** **Drawer** (few fields, flat) — reuse `TasksMutateDrawer` shape.
- **Special backend behavior:** Deleting a Division that has **any active Department** returns **409 Conflict** — does NOT cascade. UI must surface this clearly (see §5 `ResourceDeleteDialog`): message e.g. *"Cannot delete Division «X»: it still has active departments. Remove or reassign them first."* No optimistic delete.
- **List UX:** plain table; no bulk delete (single-row guard makes bulk unsafe to auto-resolve). Per-row "..." → Edit / Delete.

### 1.2 Department — module `department`
- **Fields:** `code` (unique), `name`, `description`, `division_id` (FK → Division, **required**), `manager_id` (FK → Employee, nullable).
- **List columns:** Code | Name | Division | Manager | actions.
- **Create/Edit pattern:** **Drawer**, but **Division is a required `SelectDropdown`** populated from a `useDivisions` lookup query. This is the one field-shape divergence from a flat resource.
- **Special:** No 409 documented for Department itself. Delete is plain soft-delete.

### 1.3 Subdivision — module `subdivision`
- **Fields:** `subdivision_code` (unique, required), `name` (required), `description`, `location` (required).
- **List columns:** Code | Name | Location | Description | actions.
- **Create/Edit pattern:** **Drawer** (flat).
- **Note:** `total_lots` denormalised count is **dropped from the write path** in the
  new backend (Q5). Legacy showed `total_lots`/`total_phases` as columns (see §2 note),
  but the new backend derives these via `COUNT()`; do not let the UI write them. If a
  list needs them, read from a derived field exposed by the backend, else omit.

### 1.4 Position (Employee Settings) — module `emp_settings`
- **Fields:** `code` (unique), `title` (required), `description`, `department_id` (FK → Department, nullable).
- **List columns:** Code | Title | Department | actions.
- **Create/Edit pattern:** **Drawer**; Department is an optional `SelectDropdown`.
- **Routing note:** Sidebar already has "Employee Settings" → `/employee-settings` mapped to `emp_settings`. This list backs that route (it is the `Position` CRUD, not the 201-file annex — the annex is a later phase). Keep the sidebar label but the page is Position CRUD.

### 1.5 Shifts — module `shifts` — *PLACEHOLDER SCHEMA*
- **⚠️ Placeholder pending backend confirmation (OQ-1 RESOLVED).** `phase1-design.md`
  does not define Shifts fields/endpoints; only a sidebar `permission:{module:'shifts'}`
  exists. Per decision, we **scaffold a minimal flat-resource CRUD now** using this
  best-guess schema, but implementation MUST verify the real backend Shifts
  fields/endpoints exist before building against this guess, and **flag to the user**
  if they don't match.
- **Fields (placeholder):** `code` (unique), `name` (required), `start_time` (time),
  `end_time` (time), `description` (nullable).
- **List columns:** Code | Name | Start | End | Description | actions.
- **Create/Edit pattern:** **Drawer**, matching other flat resources.
- **Permission gate:** `useCan('shifts','view'|'add'|'edit'|'delete')`.
- **Implementation note:** if the backend Shifts contract differs, update this schema
  and the `features/shifts` form; do not silently ship against an unverified guess.

### 1.6 CSV Import (Employees) — module `emp_list`
- **This is its own focused flow**, designed in §3. Backend contract: **one-row-at-a-time
  reusing `POST /employees`** (no new backend endpoint) — see OQ-2 in §7.

### 1.7 Phase — module `phase`
- **Fields:** `code` (unique), `name`, `subdivision_id` (FK → Subdivision, required).
- **List columns:** Code | Name | Subdivision | actions.
- **Create/Edit pattern:** **Drawer**; Subdivision required `SelectDropdown`.
- **Note:** `total_blocks`/`total_lots` denormalised counts dropped from write path (Q5). Phase is typically **pre-created** and then selected inside the Subdivision Wizard (see §2 step 1), not created within the wizard.

### 1.8 Owner — module `owner`
- **Fields:** `first_name`, `last_name`, `lot_no` (String), `block` (String), `email`, `contact_no`. **No** `lot_id`/`block_id` FKs (Q8 corrected).
- **List columns:** Name | Lot No | Block | Email | Contact | actions.
- **Create/Edit pattern:** **Drawer** (flat). `lot_no`/`block` are free-text display labels only — UI must not imply they link to a Lot row. Tooltip/hint: "Labels only; not linked to a lot record."

### 1.9 Models — module `models`
- **Fields:** `name` (required), `model_type_id` (FK → ModelTypes, nullable).
- **List columns:** Name | Model Type | actions.
- **Create/Edit pattern:** **Drawer**; ModelType optional `SelectDropdown`.

### 1.10 ModelTypes — module `model_types`
- **Fields:** `name`, `code` (unique), `additional_options` (bool).
- **List columns:** Code | Name | Additional Options | actions.
- **Create/Edit pattern:** **Drawer** (flat, few fields).

### 1.11 EmployeeProjects — module `emp_project`
- **Fields:** `employee_id` (FK → Employee, required), `project_id` (FK → Project, required), `date` (DateTime, nullable), `rendered_hours` (int, nullable), `task` (String, nullable), `is_assigned` (bool).
- **Unique constraint:** `(employee_id, project_id)` — duplicate assignment → 409.
- **List columns:** Employee | Project | Date | Rendered Hours | Task | Assigned | actions.
- **Create/Edit pattern:** **Drawer**, but several `SelectDropdown`s (Employee, Project). This is the entry point for the **Manpower** UI (see §4).
- **Note:** "unassign/delete" = soft delete. Duplicate-pair 409 must be surfaced.

### 1.12 Blocks / Lots — module `projects` (delete only)
- Per `phase1-design.md §2`: Blocks/Lots have **no standalone list CRUD page** in Phase 2/3. They are **created/edited inline within Phase** (nested — **OQ-3 RESOLVED: confirmed nested under Phase**) and **deleted via guarded endpoints**:
  - `DELETE /blocks/{id}` and `DELETE /lots/{id}`, gated `projects/delete`.
  - **409 Conflict** if still referenced by an **active** `Category` (`is_deleted=false`). Referenced only by soft-deleted Categories → deletable.
- **UI placement:** Blocks/Lots stay **nested under Phase's detail/edit UI** (a Phase "Blocks & Lots" sub-section), not separate top-level pages. Create/Edit of a Block happens inside the Phase drawer (or a Phase detail route). Delete uses the shared `ResourceDeleteDialog` which renders the 409 message: *"Cannot delete Block «X»: it is used by an active category. Remove the category first."*
- **Wizard note:** in the Subdivision Wizard (§2), Blocks/Lots are **selected from
  existing** (not created) — matching legacy, where the Category step populates block/lot
  dropdowns from `GET /api/blocks/{phaseId}`.

### 1.13 Category — module `category` (read-only list this pass; OQ-4 CHANGED)
- **Fields (read):** `code` (unique, nullable), `description`, `location`, `is_overhead` (bool), `project_id` (FK, required), `model_id` (FK, nullable), `phase_id` (FK, required), `blocks_id` (FK, nullable), `owner_id` (FK, nullable), `lot_id` (FK unique, nullable).
- **Scope change (OQ-4 RESOLVED — changed from prior default):** Build a **minimal
  read-only Category list/viewer this pass** — **no create/edit/delete actions**
  (full CRUD deferred). Two purposes: (a) satisfies the guard-context display need
  from the delete-conflict messages in §1.1/§1.12 (show which Category blocks a
  delete), (b) gives users visibility into saleable-unit data before full CRUD exists.
- **List columns (read-only):** Code | Project | Phase | Block | Lot | Model | Owner | Overhead?
- **List UX:** read-only table (no "..." actions this pass); row optionally links to
  the related Project/Phase for context. If a delete is blocked by an active Category,
  the conflict dialog can deep-link / name the specific Category shown in this list.

### 1.14 RBAC Roles & Access — module `administration` (Phase 3)
- **Fields (Role):** `code`, `name`, `is_system` (read-only flag), `is_active`.
- **List columns:** Code | Name | System? | Active? | actions.
- **Create/Edit pattern:** Role CRUD is **Drawer** (flat); the **Access editor** (permission matrix) is a **full dedicated route** `/roles/$roleId/access` (see §4) — too complex for a drawer.
- **System-role protection:** SADM/ADM (`is_system=true`) **cannot be deleted or have permissions zeroed** (backend-enforced). UI must surface this: delete action hidden/disabled with a tooltip *"System role — protected"*; the access editor disables toggles for `is_system` roles and shows a banner *"This is a protected system role. Permissions cannot be modified."*
- **List UX:** per-row "..." → Edit / Access / Delete(system-hidden).

---

## 2. Subdivision Wizard (Phase 3) — multi-step flow

> **✅ VERIFIED against legacy source (OQ-5 RESOLVED).** The legacy frontend
> `F:/laragon/www/wchhris` **is reachable** from this WSL environment at
> `/mnt/f/laragon/www/wchhris`. The actual wizard is
> `templates/project_management/subdivision-wizard.html.twig` + `public/assets/js/
> pages/form-wizard.init.js`. The step sequence below is **confirmed against legacy**,
> with one important divergence from the new backend noted.

**Legacy wizard — actual structure (3 tab-panes, `data-tab-id` 1/2/3):**
1. **Subdivision Details** — a `select` of an **existing** Subdivision (code:name);
   selecting it auto-fills Location + Description and populates a **Phase** dropdown
   (phases belong to the chosen subdivision). Shows Total Blocks / Total Lots for the
   phase. *(Legacy does NOT create a new Subdivision here — it reuses one.)*
2. **Category Details** — overhead toggle, **Model** select, auto-composed Description,
   **Block** select, **Lot** select (lots loaded live from `GET /api/blocks/{blockId}`),
   **Owner** select. *(Blocks/Lots are selected from existing, not created.)*
3. **Project Details** — **Project code auto-composed** from sub-code + phase-code +
   block + lot + model (via `updateProjectCode()`), plus Project name + description.
- The whole wizard submits as **ONE `POST` to `wizard_project`** (a single form post).
  There is **no sequential-create animation** in legacy; it is one server action.

**Frontendv3 wizard — adopted step order (matches legacy 1→2→3), mapped to new backend:**
Because the new backend (phase1-design.md §2) has **no `wizard_project` batch endpoint**
and exposes per-resource creates, the frontendv3 wizard keeps legacy's **user-visible
order (Subdivision → Category → Project)** but performs the writes as **sequential
backend creates** (OQ-6):

1. **Subdivision** — select an **existing** Subdivision (lookup) + select its **Phase**
   (lookup). The wizard reads (does not create) these; they must pre-exist (created via
   their own drawers / Phase nested UI). Show the phase's block/lot counts if the
   backend exposes them.
2. **Category** — overhead toggle, **Model** select (lookup), **Block** select (lookup,
   filtered by chosen Phase via `GET /blocks?phase_id=`), **Lot** select (lookup, filtered
   by chosen Block), **Owner** select (lookup), auto-composed Description. *(Mirrors
   legacy's Category step exactly: blocks/lots are selected, not created.)*
3. **Project** — **Project code auto-composed** from the selections (replicate legacy's
   `updateProjectCode()` logic: `subCode + phaseCode + 'B'+block + 'L'+lot + modelPrefix`),
   plus Project name + description; `subdivision_id` from step 1.

**What the wizard actually creates (against new backend):** on Finish it creates
**Category** (`POST /categories`) then **Project** (`POST /projects`) — in that order —
because Subdivision/Phase/Block/Lot are selected from existing records. (If the
implementation finds the new backend genuinely requires creating Phase/Block/Lot too,
extend step 1/2 to allow "add new" inline; default is select-existing per legacy.)

**State preservation between steps (f3 testRequired):**
- Wizard state lives in a **single `useWizardState` context/reducer** (not per-step local state), so navigating back/forward or closing-and-reopening the Sheet **does not lose entered data**.
- Use a `Sheet` (or stepped `Dialog`) with a `<Stepper>` header (3 steps, matching legacy). Each step reads/writes the shared context; "Next" validates only the current step's slice (zod per-step schema) before advancing.

**Commit order & failure handling (OQ-6 RESOLVED — sequential, no batch endpoint):**
- On Finish, the wizard fires **`POST /categories` then `POST /projects`** (dependency
  order: Category first since Project references it; both reference the pre-selected
  Subdivision/Phase/Block/Lot). There is **no backend batch endpoint** (legacy's
  `wizard_project` is not reproduced); each is an individual create.
- The backend has **no transaction spanning these steps**, so on a mid-sequence failure
  the already-created entity is **not** rolled back by the backend. The wizard therefore:
  - Records which steps already have a confirmed `id` (Category id after step-2 create).
  - On a failure at the Project step, shows a **partial-success report**, e.g. *"Category
    created successfully. Project creation failed: «<error from ErrorBody>». Your progress
    is saved — fix the issue and retry from this step."*
  - **Does NOT ask the user to re-enter already-succeeded steps.** Retry only re-attempts
    the failed step forward; steps with a confirmed `id` are skipped (the Category is
    reused as the FK parent for the Project).
- The `ErrorBody` of the failing step drives the message shown in the report.

**Tests:**
- *State preservation (f3):* fill step 1, advance to step 2, go **back** to step 1,
  assert values persist; close and reopen the Sheet, assert values persist (state
  hoisted above the Sheet, e.g. in the page/provider).
- *Resume-after-partial-failure (new, §8.13):* mock Category create succeeding (returns
  id) and Project create failing; assert the report names the succeeded Category, the
  wizard retains the Category id, and a retry re-attempts only the Project step (no
  duplicate `POST /categories`).

---

## 3. CSV Import (Employees) design

**Problem with the current `tasks-import-dialog`:** it only validates "a CSV file
was chosen" and calls `showSubmittedData`. It does **not** parse, preview, or
commit. We replace it with a real flow.

**Backend contract (OQ-2 RESOLVED):** **one-row-at-a-time, reusing the existing
`POST /employees` endpoint.** No new backend endpoint is required. The "batch" is a
frontend-simulated concept, not a backend-enforced transaction.

**Flow (4 stages inside one Dialog/Sheet):**
1. **Upload** — file input (`.csv` only). Client parses with **`papaparse`** (OQ-7
   RESOLVED: `papaparse` is **NOT currently in `package.json`** — it must be added as
   a dependency before implementation). Show row count.
2. **Map & Preview** — render the first N rows in a preview table; infer/let user confirm column mapping to `EmployeeRecords` fields (`employee_code`, `first_name`, `last_name`, `birthdate`, `email`, `division_id`, `department_id`, `position_id`, `employee_status`, `date_hired`, …). (Column mapping is the remaining UX detail; the endpoint is `POST /employees` per row.)
3. **Validate per row** — run the same zod field validation the single-employee form uses, **per row**. Show a per-row status: ✓ valid / ✗ error with the reason(s) inline (e.g. *"Row 4: employee_code missing; birthdate invalid date"*).
4. **Confirm & Commit** — a summary ("12 valid, 3 with errors"). User confirms. The frontend sends **each valid row as an individual `POST /employees` call**.

**Commit strategy — frontend-simulated atomicity (OQ-2 RESOLVED):**
- The frontend holds the full set of valid rows and fires one `POST /employees` per
  row (can be sequential or bounded-concurrent; must be deterministic about which
  rows succeeded).
- The import is marked **"complete" only once every row succeeds**. This atomicity is
  **simulated on the frontend** — the backend does not wrap the rows in a transaction,
  so if the browser is closed mid-import already-created rows persist. The UI must
  make clear it is row-by-row.
- **On any row failure:** report **which row(s) failed**, mapping the backend
  `ErrorBody` to a per-row message (e.g. *"Row 7: employee_code already exists (409)"*).
  Offer a **Retry** that re-submits **only the failed rows** — already-succeeded rows
  are **not** resent on retry (the frontend tracks per-row status: pending / success /
  failed).
- Legacy partial-success-on-bad-data (silent partial insert) is **not** reproduced;
  the user always sees the exact failure set and chooses to retry just those rows.

**UX states required:** empty (no file), parsing, validation summary, submitting (disable controls), success (toast + table refetch), error (row-level report + retry). Reuse the `isPending`/`isError`/Try-again pattern.

---

## 4. RBAC Roles & Access editor (Phase 3)

**Goal (f3 testRequired):** assigning a permission reflects in a **mocked
`useCan()` check**; system-role protection is surfaced in the UI.

**Layout:**
- Roles list (`/roles`) — table of roles (see §1.14). Row "..." → Edit / Access / Delete(system-hidden).
- Access editor route `/roles/$roleId/access` — a **permission matrix**:
  - Rows = modules (from a `useModules` lookup: `emp_list`, `division`, `department`, `subdivision`, `phase`, `owner`, `models`, `model_types`, `projects`, `emp_project`, `administration`, `category`, `emp_task`, `project_type`, …).
  - Columns = actions: `view` / `add` / `edit` / `delete`.
  - Each cell = a toggle (switch). Toggling calls `PATCH /rbac/roles/{id}` (or a dedicated `RolePermission` upsert) then **invalidates the permissions query** so `useCan()` recomputes.
- **Mock test:** render the editor with a stubbed `PermissionsProvider` value; toggle a cell; assert a component using `useCan(module, action)` flips from `false`→`true` (and back). This directly satisfies f3's "assigning a permission reflects in a mocked useCan() check".

**System-role protection (UI, not just backend):**
- In the list, system roles (`is_system=true`) show a lock icon; the Delete menu item is hidden/disabled with tooltip *"Protected system role"*.
- In the Access editor for a system role, all toggles are `disabled` and a banner shows *"This is a protected system role (SADM/ADM). Permissions cannot be modified."*
- Attempting to zero permissions (all toggles off) for a system role is blocked client-side **and** the backend rejects it — surface the 409/403 with a clear message.

---

## 5. Shared components to extract (avoid 8× duplication)

The tasks feature already duplicates a lot of the employees pattern. For this pass,
**propose extracting these shared building blocks** rather than copying
`tasks-*` per resource:

1. **`<ResourceCrudDrawer>`** (new, in `components/resource-crud-drawer.tsx`)
   - Generic `Sheet` + `Form` + `react-hook-form` + `zodResolver` scaffold.
   - Props: `schema`, `defaultValues`, `fields` (render prop or field-config), `isUpdate`, `onSubmit`, `isPending`.
   - Replaces the per-resource copy of `tasks-mutate-drawer.tsx`. Division/Department/Subdivision/Position/Shifts/Phase/Owner/Models/ModelTypes/EmployeeProjects/Roles all use it.
2. **`<ResourceDeleteDialog>`** (new, wraps `ConfirmDialog`)
   - Props: `open`, `onOpenChange`, `entityName`, `entityLabel`, `onConfirm`, `isPending`, `conflictError?`.
   - Renders the generic warning **and** maps a 409 `ErrorBody` to a friendly
     message. Each resource passes its specific 409 copy (e.g. Division/Department
     guard, Blocks/Lots guard). This is the single place the 409-messaging
     requirement (brief §1 "clear messaging when a delete is blocked by a 409")
     is implemented.
3. **`<ResourceTable>`** (optional, if time permits) — a thin wrapper that takes
   `columns`, `data`, `count`, and the `useTableUrlState` config, rendering
   `DataTableToolbar` + `Table` + `DataTablePagination` + the standard
   loading/empty/error states. Reuses the employees `isPending`/`isError` block.
   This guarantees the "consistent empty/loading/error states" requirement.
4. **Permission-aware action button helpers** — a `<CanCreate>`/`<CanDelete>`
   wrapper or a `useCanAction(module, action)` that returns both the boolean and
   the gate, so every page uses one idiom instead of ad-hoc `canView &&`.
5. **CSV import flow component** — `<CsvImportWizard>` (in `features/employees/
   components/csv-import/`) encapsulating the 4 stages from §3, reusable if other
   resources later need CSV import.

> Decision: extract #1, #2, #5 as **required** for this pass (high duplication
> payoff + they encode the 409/permission/CSV requirements centrally). #3/#4 are
> **recommended** but can be deferred if the executor prefers per-page tables that
> already mirror employees.

---

## 6. Component / file structure

Follow the existing `features/<resource>/` + `routes/_authenticated/<resource>/`
convention. Each CRUD resource gets:

```
frontendv3/src/features/<resource>/
  index.tsx                      # page: Header + Main + <Resource/>Table + Dialogs + Provider
  index.test.tsx
  data/
    schema.ts                    # zod schema + TS type (Create/Update/Public)
  components/
    <resource>-table.tsx         # TanStack table (reuse ResourceTable if extracted)
    <resource>-columns.tsx       # ColumnDef[]
    <resource>-row-actions.tsx   # "..." dropdown (if >2 actions)
    <resource>-provider.tsx      # dialog state context (currentRow + open)
    <resource>-dialogs.tsx       # renders drawer(s) + delete dialog
    <resource>-mutate-drawer.tsx # (only if NOT using shared ResourceCrudDrawer)
  (csv-import/ for employees)

frontendv3/src/lib/api/<resource>.ts   # fetch + useQuery hooks, query keys
frontendv3/src/routes/_authenticated/<resource>/
  index.tsx                              # createFileRoute, validateSearch (page/pageSize/q)
  (optional) $id/access.tsx              # RBAC access editor route
```

**Concrete new features folders:**
- `features/divisions`, `features/departments`, `features/subdivisions`,
  `features/employee-settings` (Position), `features/shifts`,
  `features/phases`, `features/owners`, `features/models`,
  `features/model-types`, `features/employee-projects`, `features/roles`
  (+ `features/roles/$roleId/access` or a `roles-access` feature).
- `features/categories` — **list-only viewer this pass** (OQ-4): `index.tsx` +
  `index.test.tsx` + `data/schema.ts` + `components/categories-table.tsx` +
  `components/categories-columns.tsx`. **No mutate-drawer, no row-action delete.**
- Subdivision Wizard: `features/subdivisions/components/subdivision-wizard.tsx`
  (+ `use-wizard-state.tsx` context; 3 steps Subdivision → Category → Project;
  tracks per-step confirmed `id` for resume; replicates legacy `updateProjectCode()`
  composition for the Project code).
- CSV import: `features/employees/components/csv-import/` (uses `papaparse`, which
  must be added to `package.json`).

**Sidebar (`sidebar-data.ts`) additions:** Division/Department/Subdivision/Employee
Settings/Shifts already exist. Add: Phases, Owners, Models, Model Types, Employee
Projects, Categories (read-only viewer), Roles (under Administration group), and a
"Subdivision Wizard" entry (the wizard route reuses `/subdivisions` or a dedicated
`/subdivisions/wizard`).

**Permissions wiring:** every new route's `index.tsx` gates `useCan('<module>','view')` at the top (mirror `EmployeesAuthGate`). Sidebar items already carry `permission:{module}` so non-permitted nav items hide automatically.

---

## 7. Open questions — ALL RESOLVED

- **OQ-1 — Shifts schema/endpoints. ✅ RESOLVED.** Scaffold a minimal flat-resource
  CRUD now with **placeholder** fields (`code` unique, `name`, `start_time`, `end_time`,
  `description`). Implementation must verify the real backend Shifts fields/endpoints
  exist and **flag to the user** if the guess is wrong (see §1.5 warning). Full CRUD
  deferred until backend contract confirmed.
- **OQ-2 — CSV import backend contract. ✅ RESOLVED.** One-row-at-a-time reusing the
  existing `POST /employees` endpoint — **no new backend endpoint**. Frontend holds
  all rows, fires one `POST /employees` per valid row, marks complete only when all
  succeed (frontend-simulated atomicity), and offers retry of **only failed rows** on
  failure. See §3.
- **OQ-3 — Blocks/Lots pages vs. nested. ✅ RESOLVED (confirmed nested).** Blocks/Lots
  stay **nested under Phase** (no separate top-level routes), matching the backend's
  "write folded into Phase create/update". No change beyond marking resolved.
- **OQ-4 — Category UI surface. ✅ RESOLVED (changed from default).** Build a **minimal
  read-only Category list/viewer this pass** (Code | Project | Phase | Block | Lot |
  Model | Owner | Overhead?). No create/edit/delete. Serves guard-context display + user
  visibility. See §1.13 and §6.
- **OQ-5 — Legacy Subdivision Wizard step sequence. ✅ RESOLVED (VERIFIED).** Legacy
  `F:/laragon/www/wchhris` **is reachable** at `/mnt/f/laragon/www/wchhris`. Confirmed
  from `templates/project_management/subdivision-wizard.html.twig` + `form-wizard.init.js`:
  the real wizard is **3 steps in order Subdivision → Category → Project**, where
  Subdivision/Phase are **selected from existing** (not created), Blocks/Lots are
  **selected** in the Category step (loaded from `GET /api/blocks/{id}`), and the Project
  code is **auto-composed** client-side. It submitted as one `POST wizard_project`.
  **Correction vs. prior draft:** the earlier reconstruction (Subdivision → Project →
  Phase → Blocks/Lots → Category, creating everything) was **wrong** — legacy does not
  create Phase/Block/Lot in the wizard. frontendv3 adopts legacy's visible order and
  select-existing semantics, but performs **sequential creates of Category then Project**
  against the new backend (no `wizard_project` batch). See §2.
- **OQ-6 — Wizard atomicity. ✅ RESOLVED.** **Sequential creates in dependency order**
  (Category → Project; Subdivision/Phase/Block/Lot pre-selected). **No backend batch
  endpoint.** On mid-sequence failure: partial-success report naming succeeded steps,
  retain confirmed step IDs, retry only re-attempts the failed step forward (no
  re-entry / no duplicate creates of earlier steps). See §2.
- **OQ-7 — CSV parser dependency. ✅ RESOLVED.** Use **`papaparse`**. It is **NOT
  present in `frontendv3/package.json`** today — must be added as a dependency before
  implementation. See §3 and §6.

---

## 8. Test plan (maps to `frontend-phases.json` testsRequired)

### f2 testsRequired
1. **DataTable sorting/pagination tests** — for each new list (start with
   Division + Department as the template, then replicate): assert clicking a
   sortable header reorders; assert page-size change and next/prev page update the
   URL search (`page`/`pageSize`) and the rendered rows. Reuse the employees
   `useTableUrlState` contract.
2. **Modal open/close/focus-trap tests** — for `ResourceCrudDrawer` (and the
   legacy `tasks-mutate-drawer` parity): assert opening focuses the first field,
   Escape/close returns focus to the trigger, and focus is trapped inside the
   Sheet while open (Radix `Sheet` provides this; assert via the dialog role +
   `aria-modal`).
3. **One full CRUD flow test (template)** — pick **Department** as the canonical
   end-to-end: create (fills drawer, submits, row appears in table after refetch),
   edit (changes a field, persists), delete (confirm dialog → row disappears).
   This template is then copied per resource. Assert server-state via
   `useQuery` invalidation (row count / presence), not optimistic DOM.

### f3 testsRequired
4. **RBAC editor → mocked `useCan()`** — render the Access editor inside a stubbed
   `PermissionsProvider`; toggle a module/action cell; assert a child using
   `useCan(module, action)` flips accordingly (and the permissions query is
   invalidated). Directly satisfies f3's requirement.
5. **Subdivision Wizard state-preservation** — fill step 1, advance to step 2, go
   back to step 1, assert values persist; close and reopen the Sheet, assert
   values persist (state hoisted above the Sheet). Satisfies f3's requirement.

### Permission-gate tests (per resource)
6. For **every** resource, a test renders the list with a **mocked low-privilege
   `MyPermissions`** (no `add`/`edit`/`delete` for that module). Assert:
   - Create button is absent/hidden.
   - Row "..." menu shows no Edit/Delete (or they are disabled).
   - Navigating directly to a create/edit route still shows a permission-denied
     state (defense in depth, mirrors `EmployeesAuthGate`).
   Use the employees `useCan` gating as the reference assertion.
   - **Category list (§1.13) is read-only**, so its gate test asserts only `view`
     gating and that **no** create/edit/delete controls exist at all.

### 409-conflict handling tests
7. **Division delete with active Departments** — mock `DELETE /divisions/{id}` to
   return 409 with an `ErrorBody` referencing departments; assert the
   `ResourceDeleteDialog` shows the specific *"still has active departments"*
   message (not a generic error) and the row is **not** removed from the table
   (no silent failure, no optimistic delete).
8. **Blocks/Lots delete with active Category** — same pattern for
   `DELETE /blocks/{id}` / `DELETE /lots/{id}` returning 409; assert the
   Category-specific message and no row removal.
9. **EmployeeProjects duplicate pair** — mock create returning 409 on duplicate
   `(employee_id, project_id)`; assert the drawer surfaces the conflict and does
   not close/optimistically add.

### CSV import tests
10. Upload non-CSV → validation error. Upload CSV → preview table renders.
    Inject a row with a missing required field → per-row error shown with reason.
    Confirm step disabled until 0 invalid rows (or clearly reports them). On
    commit, assert each valid row is sent as an individual `POST /employees` and
    the table refetches on full success; on a backend error for a row, assert a
    row-level error report mapped from `ErrorBody` and **no partial insert is
    presented as success**.
11. **CSV retry sends only failed rows (new).** Mock 10 valid rows where rows 3 and 7
    fail (`POST /employees` → 409/422); rows 1,2,4,5,6,8,9,10 succeed. Assert the
    report lists exactly rows 3 and 7 as failed. Trigger Retry; assert **only rows 3
    and 7 are re-POSTed** (successful rows are NOT resent) and, on their success, the
    import is marked complete. Verifies the "retry only failed rows" contract from §3.

### Subdivision Wizard tests
12. **Wizard state-preservation** — covered by f3 test #5 above.
13. **Wizard resume-after-partial-failure (new).** Mock Category create (`POST
    /categories`) succeeding (returns id), Project create (`POST /projects`) failing
    with an `ErrorBody`. Assert: (a) the partial-success report names the Category as
    created, (b) the wizard context retains the Category id, (c) a Retry re-attempts
    **only the Project step** (no second `POST /categories` is fired), (d) on Project
    success the wizard completes. Verifies the OQ-6 resume contract from §2. Also
    assert the 3-step order (Subdivision → Category → Project) matches legacy (OQ-5).

### Consistency regression
14. Every new list page asserts the three states (loading skeleton / empty "No
    results" / error + Try-again) using the shared pattern, so a missing state
    fails the test. (Reuse employees' `isPending`/`isError` block as the fixture.)
    Include the **Category read-only list** in this regression.
