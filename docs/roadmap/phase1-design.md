# Phase 1 — Employee core + Org structure: Design (APPROVED)

> **APPROVED design** — all 12 open decisions are finalized (§4) and an indexing/
> constraint section is added (§7). This document is the implementation-ready
> reference. No code has been written yet. `docs/roadmap/backend-phases.json`
> `b1` checkboxes stay `false` until implementation happens in a later task.
>
> Scope source: `docs/roadmap/backend-phases.json` `b1` (6 items, 2 tests) +
> `REWRITE_ROADMAP.md` Phase 1 + the privilege-escalation bug. The legacy source
> was read at `/mnt/f/laragon/www/wchhris-api` and the schema reference at
> `analysis/01-backend-datamodel.md`. Phase 0 foundation (`app/rbac`,
> `app/common`, `app/user`) is the fixed base — this design builds on it, never
> reinvents it.

## 0. Non-negotiable constraints inherited from Phase 0

- **Auth + RBAC are already real.** Every route that mutates or reads data MUST be
  either authenticated or explicitly declared in `app/common/route_policy.py`
  `PUBLIC_ROUTES`. The `tests/rbac/test_route_protection.py` suite fails the build
  for any route that is neither. Every gated resource route uses
  `Depends(require_permission(module, action))` from
  `app.rbac.dependencies` (see `app/rbac/routes.py` for the established pattern).
- **No privilege escalation.** The legacy `UsersController::updateUser()` accepted a
  `user_type` body field and assigned any role; `SuperAdminController` had no
  super-admin check; `revalidate-session` minted a JWT for any `user_id`; `/signup`
  was outside the firewall with caller-chosen role. None of these are reproduced.
  The Phase 0 fix is structural: there is no `user_type` field on any self-editable
  schema, and role changes go through a dedicated admin-only endpoint.
- **Money = `Decimal`/`NUMERIC`** (Phase 0 adopted this; Phase 1 entity fields that
  are money use `Decimal`). The construction/manpower entities in `b1` carry no
  money columns, so this mainly matters for later phases; flagged for awareness.
- **Soft delete is `is_deleted` boolean (`NOT NULL DEFAULT false`)**, applied
  uniformly — NOT the legacy three-way `archived`/`isArchived`/`removed` mess.
  List endpoints filter `is_deleted = false`. This is the one naming/behaviour
  deviation from legacy that is deliberate and required.

---

## 1. Data model

Conventions for every table below:

- **PK:** `id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)`
  (replaces legacy `INT AUTO_INCREMENT` — matches Phase 0 `User`/`Role`/`Module`).
- **Snake_case, singular table names** via `__tablename__`. The legacy names are
  noted per entity in a *Legacy name* line so the Phase 6 ETL mapping is traceable.
- **Soft delete:** every mutable entity gets `is_deleted: bool = Field(default=False,
  index=True)` and `deleted_at: datetime | None = None`. (Legacy `archived`
  `isArchived`/`removed` → unified `is_deleted`.)
- **Timestamps:** `created_at` / `updated_at` `TIMESTAMP` (`DateTime(timezone=True)`),
  `server_default=func.now()` for `created_at`, set in services for `updated_at`.
  Legacy had no lifecycle callbacks (see datamodel §1.4) — we add them deliberately.
- **FKs:** `ondelete="CASCADE"` where the parent's deletion should cascade,
  `SET NULL` otherwise. Legacy had all FKs `RESTRICT` with no cascade; we make the
  cascade policy explicit per relationship below.
- **Types:** `VARCHAR` → `String(n)`; `TINYINT(1)` → `Boolean`; `DATETIME` →
  `DateTime`; `DATE` → `Date`; `INT` count → `int`; legacy `zip_code SMALLINT`
  (overflows PH ZIP) → `String(10)`; legacy `attachment_size VARCHAR` → `int`.

### 1.1 Employee & HR core

#### `EmployeeRecords` — *legacy `employee_records`*
Master HR record. One row per person.

| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | — | legacy `id INT` |
| `employee_code` | String(32), unique=True, index=True | No | legacy `employee_code` VARCHAR(255) NOT unique/indexed. **We add unique+index** — it's the business key used everywhere (`findByCode`) |
| `first_name` | String(255) | No | |
| `middle_name` | String(255) | Yes | |
| `last_name` | String(255) | No | |
| `extension` | String(32) | Yes | |
| `birthdate` | Date | No | legacy `DATETIME` but only date used → `Date` |
| `birth_place` | String(255) | Yes | |
| `gender` | String(32) | No | free `VARCHAR(255)`; kept as plain `String` (Q2: not an enum) |
| `civil_status` | String(32) | No | kept as plain `String` (Q2: not an enum) |
| `email` | String(255) | Yes | |
| `zip_code` | String(10) | Yes | legacy `SMALLINT` overflows PH ZIP → `String` |
| `area` | String(255) | Yes | |
| `present_barangay` | String(255) | Yes | |
| `present_city` | String(255) | Yes | |
| `same_address` | bool | Yes | |
| `permanent_barangay` | String(255) | Yes | |
| `permanent_city` | String(255) | Yes | |
| `date_hired` | Date | Yes | legacy `DATETIME`, made nullable |
| `employee_status` | `EmployeeStatusEnum` (str Enum) | No | (Q2) `str` Enum: `ACTIVE="Active"`, `RESIGNED="Resigned"`, `TERMINATED="Terminated"`, `ON_LEAVE="On Leave"` — values taken from legacy literals. Stored as VARCHAR; `ACTIVE` is the default/literal used in queries |
| `position_id` | UUID FK → `Position.id`, nullable=True | Yes | (Q3) legacy `position` was free text — now a real FK; free-text field removed entirely |
| `employment_type` | String(64) | Yes | free text, NOT FK to `contract_types` |
| `contract_expiry_date` | Date | Yes | |
| `date_separated` | Date | Yes | |
| `probationary_date` | Date | Yes | |
| `regularization_date` | Date | Yes | |
| `telephone` | String(32) | Yes | |
| `cellphone` | String(32) | Yes | |
| `profile_photo_path` | String(512) | Yes | filesystem path, not blob |

Relationships:
- `division_id` → `Division.id` (FK, nullable, legacy `division_id`)
- `department_id` → `Department.id` (FK, nullable)
- `user_id` → `User.id` (FK, nullable, legacy OneToOne `user`)
- `affiliated_company_id` → `AffiliatedCompany.id` (FK, nullable)

**`position` is a real FK (Q3):** legacy `EmployeeRecords.position` was a free-text
string, but `b1` lists `Position` as a CRUD resource. This design stores
`position_id` (FK → `Position.id`, nullable) and removes the free-text `position`
field entirely. Legacy free-text position values must be resolved/created against the
new `Position` table during the Phase 6 ETL (see §6).

#### `EmployeeAdditionalRecords` — *legacy `employee_additional_records`*
201-file annex. 11 JSON blobs in legacy. **We keep the JSON columns** (normalising
them into tables is out of scope for Phase 1) but type them as `JSON` (native
Postgres JSONB), not the legacy `Type::ARRAY` PHP-serialised blobs.

| Field | Type | Null |
|---|---|---|
| `id` | UUID PK | |
| `employee_id` | UUID FK → `EmployeeRecords.id`, unique=True | No |
| `employment_history` `past_employment_record` `educational_background` `seminars_trainings` `assessments_exams` `skills` `awards` `licenses` `dependents` `violations` `medical_drug_tests` | JSON | Yes |
| `school_graduated` `course` `career_band_level` `career_global_grade` `cash_card_number` `hmo_account` `sss_number` `philhealth_number` `pagibig_number` `tin_number` | String(255) | Yes |

**Security:** these hold SSS/TIN/violations/medical data. The legacy
`EmployeeRecordsController` exposed them to **any** authenticated user by code with
no ownership check. Phase 1 routes are gated by `require_permission("emp_list",
"view")` and, where applicable, an ownership check so a non-privileged employee only
reads their own annex. (Ownership-scoped read extends the `Item` owner pattern in
`app/item/routes/items.py`.)

#### `EmployeeAttachments` — *legacy `employee_attachments`*
| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | | |
| `employee_id` | UUID FK → `EmployeeRecords.id` | No | legacy `employee_id` |
| `type` | String(64) | Yes | legacy free-text doc category |
| `attachment_name` | String(255) | Yes | |
| `attachment_size` | int | Yes | **legacy was VARCHAR → int bytes** |
| `file_path` | String(512) | Yes | legacy `file` (path) |
| `original_file_name` | String(255) | Yes | |
| `date_uploaded` | DateTime | Yes | set in service |

We add `is_deleted` for consistency. **Files are stored on disk/object storage; only
paths live in the DB** (matches legacy, and the roadmap forbids the public web-root
CSV pattern).

### 1.2 Org structure

#### `Division` — *legacy `division` (soft-delete was `isArchived`)*
| Field | Type | Null |
|---|---|---|
| `id` | UUID PK | |
| `code` | String(32), unique=True | No |
| `name` | String(255) | No |
| `description` | String(1024) | Yes |
| `director_id` | UUID FK → `EmployeeRecords.id`, nullable | Yes |

Relationships: `departments` (one→many `Department`), `employee_records`
(one→many). **Cascade policy (Q4):** deleting a Division with any active
(`is_deleted = false`) Department children returns **409 Conflict** and does NOT
cascade or orphan them. No re-parenting logic. `is_deleted` replaces `isArchived`.

#### `Department` — *legacy `department` (soft-delete was `isArchived`)*
| Field | Type | Null |
|---|---|---|
| `id` | UUID PK | |
| `code` | String(32), unique=True | No |
| `name` | String(255) | No |
| `description` | String(1024) | Yes |
| `division_id` | UUID FK → `Division.id` | No |
| `manager_id` | UUID FK → `EmployeeRecords.id`, nullable | Yes |

#### `Subdivision` — *legacy `subdivision` (soft-delete `archived`)*
Top of the construction location tree.
| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | | |
| `subdivision_code` | String(32), unique=True | No | legacy `subdivision_code`; body field was `code` |
| `name` | String(255) | No | |
| `description` | String(1024) | Yes | legacy body field `desc` |
| `location` | String(255) | No | |

Relationships: `project` (one→many `Project`), `phases` (one→many `Phase`).
`is_deleted` replaces `archived`.

> **Q5 (denormalised counts):** `Subdivision.total_lots` is dropped from the write
> path. It is not stored as a writable column; the lot count is derived via a
> `COUNT()` query in list/read serializers when needed. (If keeping a nullable column
> for migration fidelity proves simpler, it may remain but the API must never write
> to it — only read paths compute it live.)

#### `Position` — *legacy: no entity; `EmployeeRecords.position` was free text*
New lookup table (required by `b1` checklist as a CRUD resource).
| Field | Type | Null |
|---|---|---|
| `id` | UUID PK | |
| `code` | String(32), unique=True | No |
| `title` | String(255) | No |
| `description` | String(1024) | Yes |
| `department_id` | UUID FK → `Department.id`, nullable | Yes |

### 1.3 Construction / manpower domain

Location hierarchy: **Subdivision → Phase → Blocks → Lots → Category**, with
`Project` (child of Subdivision) and `Category` joining Project+Phase+Blocks+Lots+
Model+Owner. `Model` → `ModelTypes`; `Owner` is the buyer.

#### `Project` — *legacy `project`*
| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | | |
| `code` | String(32), unique=True | No | |
| `name` | String(255) | No | |
| `description` | String(1024) | Yes | legacy body `desc` |
| `subdivision_id` | UUID FK → `Subdivision.id` | No | |
| `project_type_id` | UUID FK → `ProjectType.id`, nullable | Yes | (Q6) `ProjectType` table created; FK is a real, populated relationship (basic CRUD under `project_type` module, see §2) |

Relationships: `categories` (one→many `Category`). `is_deleted` replaces `archived`.

#### `ProjectType` — *legacy `project_type` (referenced by FK but 0 actual usage in legacy code)*
New lookup table (Q6 — reverses the original "skip" recommendation).
| Field | Type | Null |
|---|---|---|
| `id` | UUID PK | |
| `code` | String(32), unique=True | No |
| `name` | String(255) | No |
| `description` | String(1024) | Yes |
| `is_deleted` | bool, default=False, index=True | Yes |
| `deleted_at` | DateTime | Yes |

#### `Phase` — *legacy `phase`*
| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | | |
| `code` | String(32), unique=True | No | |
| `name` | String(255) | No | |
| `subdivision_id` | UUID FK → `Subdivision.id` | No | |

Relationships: `blocks` (one→many `Blocks`), `categories` (one→many `Category`).

> **Q5 (denormalised counts):** `Phase.total_blocks` and `Phase.total_lots` are
> dropped from the write path. They are not stored as writable columns; block/lot
> counts are derived via `COUNT()` queries in list/read serializers when needed.

#### `Blocks` — *legacy `blocks` (NO soft-delete in legacy)*
| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | | |
| `block_name` | String(255) | No | |
| `phase_id` | UUID FK → `Phase.id` | No | |
| `is_deleted` | bool, default=False, index=True | Yes | (Q7) added — legacy had none |
| `deleted_at` | DateTime | Yes | (Q7) added |

> **Q5 (denormalised counts):** `Blocks.total_lots` is dropped from the write path
> (derived via `COUNT()` when needed).
> **Q7 (delete guard):** delete endpoints for `Blocks` return **409 Conflict** if the
> row is still referenced by an **active** `Category` — i.e. a `Category` row where
> `is_deleted = false` and `blocks_id = :id`. A Block referenced *only* by soft-deleted
> Categories (or by none) is deletable. The guard query must be explicit:
> `WHERE blocks_id = :id AND is_deleted = false`, NOT a bare existence check on the FK.

#### `Lots` — *legacy `lots` (NO soft-delete, NO CRUD surface in legacy)*
| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | | |
| `lot_num` | int | Yes | |
| `lot_name` | String(64) | Yes | |
| `blocks_id` | UUID FK → `Blocks.id` | No | legacy join col `blocks_id` (note legacy typo: `blocks_id` not `block_id`) |
| `category_id` | UUID FK → `Category.id`, unique=True, nullable | Yes | legacy OneToOne `lots`⇄`category` |
| `is_deleted` | bool, default=False, index=True | Yes | (Q7) added — legacy had none |
| `deleted_at` | DateTime | Yes | (Q7) added |

A proper `category_id` FK is added (legacy modeled the link from `Category` side).

> **Q7 (delete guard):** delete endpoints for `Lots` return **409 Conflict** if the row
> is still referenced by an **active** `Category` — i.e. a `Category` row where
> `is_deleted = false` and `lot_id = :id`. A Lot referenced *only* by soft-deleted
> Categories (or by none) is deletable. The guard query must be explicit:
> `WHERE lot_id = :id AND is_deleted = false`, NOT a bare existence check on the FK.

#### `Category` — *legacy `category`*
The saleable house-and-lot unit.
| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | | |
| `code` | String(32), unique=True | Yes | |
| `description` | String(1024) | Yes | |
| `location` | String(255) | Yes | **computed in legacy; we store explicitly** |
| `is_overhead` | bool | Yes | legacy `isOverhead` |
| `project_id` | UUID FK → `Project.id` | No | |
| `model_id` | UUID FK → `Model.id`, nullable | Yes | |
| `phase_id` | UUID FK → `Phase.id` | No | |
| `blocks_id` | UUID FK → `Blocks.id`, nullable | Yes | |
| `owner_id` | UUID FK → `Owner.id`, nullable | Yes | |
| `lot_id` | UUID FK → `Lots.id`, unique=True, nullable | Yes | replaces legacy redundant scalar `block`/`lot` ints |

**Cascade note:** legacy `Category` carried redundant scalar `block`/`lot` ints
duplicating `blocks_id`/`lots_id` — dropped. `is_deleted` replaces `archived`.

#### `Model` — *legacy `model` (NO soft-delete; legacy hard-deleted)*
| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | | |
| `name` | String(255) | No | |
| `model_type_id` | UUID FK → `ModelTypes.id`, nullable | Yes | legacy `type_id` |

We add `is_deleted` (uniform).

#### `ModelTypes` — *legacy `model_types`*
| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | | |
| `name` | String(255) | Yes | |
| `code` | String(32), unique=True | Yes | |
| `additional_options` | bool | Yes | legacy `additional_options` (body field `add_option`) |

`is_deleted` replaces `archived`.

#### `Owner` — *legacy `owner`*
Buyer of a Category. **Relationship is mediated by `Category`** (see Point 3 / Q8 below).
| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | | |
| `first_name` | String(255) | Yes | legacy `firstname` |
| `last_name` | String(255) | Yes | legacy `lastname` |
| `lot_no` | String(32) | Yes | legacy `lot_no` (string) — **denormalised label only** |
| `block` | String(32) | Yes | legacy `block` (string) — **denormalised label only** |
| `email` | String(255) | Yes | |
| `contact_no` | String(32) | Yes | legacy `contact_no` (body field `contact`) |

`is_deleted` replaces `archived`.

> **Q8 (CORRECTED — relationship interpretation):** Legacy `Owner` has **no** FK to
> `Lots` or `Blocks`. It only carries denormalised `lot_no`/`block` **strings**, and its
> one real association is the inverse `OneToMany` to `Category` (`Category.owner_id`).
> The authoritative link to a physical lot runs **`Owner` → `Category` → `Lots`**, because
> `Category` owns both `owner_id` (FK → Owner) and the 1:1 `lots` (FK → Lots). `Lots`
> has no relationship back to `Owner` at all.
>
> Therefore **`Owner.lot_id` / `Owner.block_id` FKs are NOT added** (the earlier Q8 draft
> that introduced them was incorrect — it duplicated `Category`'s authoritative links and
> would let an Owner row and a Category row disagree about which Lot they reference).
> Instead:
> - Keep `Owner.lot_no` / `Owner.block` as **denormalised `String` columns** (display
>   convenience only; not joinable to `Lots`/`Blocks` and not authoritative).
> - Ownership queries go through `Category`: `Category.owner_id` + `Category.lot_id`
>   (the legacy OneToOne `Category.lots`). To find "the Owner of Lot X", read
>   `Category` where `lot_id = X`; the `Owner` is `Category.owner`.
> - **§2 / §6 updates:** Owner create/update payloads take `lot_no`/`block` **strings**
>   (not FKs); the Phase 6 ETL copies legacy `lot_no`/`block` text verbatim into these
>   columns (no FK resolution required, so there are no unresolvable-row failures to
>   flag). Optionally the ETL may *enrich* `Category.lot_id`/`owner_id` from these
>   strings, but the strings themselves remain on `Owner` as legacy fidelity.

### 1.4 Assignments / tasks

#### `EmployeeProjects` — *legacy `employee_projects`*
Assignment of an employee to a project.
| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | | |
| `employee_id` | UUID FK → `EmployeeRecords.id` | No | legacy `employee_id` |
| `project_id` | UUID FK → `Project.id` | No | |
| `date` | DateTime | Yes | legacy `Date` (PascalCase `$Date` → col `date`) |
| `rendered_hours` | int | Yes | legacy `int` (note `EmpTask.assigned_hours` was `float` — inconsistent; we keep int here) |
| `task` | String(512) | Yes | |
| `is_assigned` | bool | Yes | |

`is_deleted` replaces `archived`. `UniqueConstraint(employee_id, project_id)` to
prevent the legacy duplicate-assignment bug (assign-workers re-post).

#### `EmpTask` — *legacy `emp_task`*
Timesheet line: hours booked against a project assignment on a date.
| Field | Type | Null | Legacy note |
|---|---|---|---|
| `id` | UUID PK | | |
| `emp_project_id` | UUID FK → `EmployeeProjects.id` | No | legacy `emp_project_id` |
| `task_desc` | String(512) | Yes | legacy `task_desc` (body field `task_name`) |
| `rendered_hours` | int | Yes | legacy `int` |
| `assigned_hours` | Decimal(6,2) | Yes | legacy `float` → `Decimal` |
| `date` | DateTime | Yes | |
| `approved` | bool | Yes | |
| `is_adjusted` | bool | Yes | |
| `worker_logs_id` | UUID FK → `WorkerLogs.id`, nullable | Yes | **Phase 2 territory** — FK nullable now, wired in Phase 2 |

`is_deleted` replaces `archived`. **Approval gate (Q9):** `approve`/`deny` endpoints
are gated by `Depends(require_permission("emp_project", "edit"))` — no new permission
module is added in Phase 1. The endpoints are provided now; only the gate differs from
legacy (which had none).

### 1.5 Users / UserType

`User` already exists (Phase 0, `app/user/models.py`) with `role_id` FK →
`Role` (`app/rbac/models.py`, the normalized replacement for legacy `UserType`).
`Role` already has `code` (legacy `user_code`), `name`, `is_system`, `is_active`.
There is **no `removed` column** (Phase 0 replaced legacy `removed` with the
`is_active` flag). So Phase 1 "UserType CRUD" = **`Role` CRUD** on the existing
`app/rbac/models.py.Role` + `RolePermission` rows. No new `UserType` table.

`User` additions for Phase 1 (optional, only if needed by `b1`): `username`
(String(255), unique), `is_assignable_proj` (bool), `is_worker` (bool),
`is_straight_time` (bool) — these existed on legacy `User` and are referenced by the
construction/manpower assignment logic. **Recommendation:** add `username` (unique)
now for login-by-identifier parity, defer `is_assignable_proj`/`is_worker` to the
assignment work within Phase 1 if the bulk-update endpoints are in scope, else defer
to Phase 2.

### 1.6 Dashboard KPI read models

No new table. A `DashboardService` computes the 9 legacy KPIs as **counts**, with the
legacy bugs fixed (Q10 finalizes the daily-count fix):
- `employee_records`, `divisions`, `departments`, `projects`, `subdivisions`,
  `owners`, `employee_projects` counts → `WHERE is_deleted = false`.
- `model_count` (legacy `facilitiesCount`) → **also filtered `is_deleted = false`**
  (legacy bug counted archived models).
- `dtr_records_daily_count` → count **DISTINCT employees** with at least one worker log
  today (legacy counted raw log rows, double-counting multi-punch employees), using an
  **explicit Asia/Manila timezone boundary** for "today" (not server-local/UTC). This
  is a finalized decision (Q10), not an open question.

---

## 2. Endpoint map

Each resource gets a router under a new app package (e.g. `app/employee`,
`app/org`, `app/manpower`, `app/rbac` for role CRUD). All list/create/update/delete
routes carry `require_permission(<module>, <action>)`. Module codes are the Phase 0
seed codes (`app/rbac/seed.py`): `emp_list`, `division`, `department`,
`subdivision`, `phase`, `owner`, `models`, `model_types`, `projects`,
`emp_project`, `administration` (for role CRUD), `emp_settings` (employee 201-file),
`category` (Q11, new), `emp_task` (Q11, new), `project_type` (Q6, new).

> Note: legacy `UserAccessValidation` had **no submodule for `project`, `category`,
> `blocks`, `lots`, `employee201`, `emp_task`** — so those legacy areas were
> structurally unprotectable. Phase 0 already seeds `projects` and `emp_project`. Q11
> adds two new module codes to `app/rbac/seed.py` `SUBMODULES`: `category` and
> `emp_task`, so those resources are now gated cleanly (see endpoint map). `employee201`
> remains gated under `emp_list` (employee records) for Phase 1.

| Resource | Module | Routes | Permission (module/action) |
|---|---|---|---|
| **EmployeeRecords** | `emp_list` | `GET /employees`, `POST /employees`, `GET /employees/{id}`, `PATCH /employees/{id}`, `DELETE /employees/{id}` | view / add / edit / delete |
| | `emp_list` | `GET /employees/me` (self + own annex) | own record; ownership check |
| **EmployeeAdditionalRecords** | `emp_list` (+ ownership) | `GET/PATCH /employees/{id}/additional-records` | view/edit (admin) or self-only |
| **EmployeeAttachments** | `emp_list` | `GET/POST/DELETE /employees/{id}/attachments[/...]` | view/add/delete |
| **Division** | `division` | list/create/read/update/delete | view/add/edit/delete |
| **Department** | `department` | list/create/read/update/delete | view/add/edit/delete |
| **Subdivision** | `subdivision` | list/create/read/update/delete | view/add/edit/delete |
| **Position** | `emp_settings` | list/create/read/update/delete | view/add/edit/delete |
| **Project** | `projects` | list/create/read/update/delete + `GET /projects/summary` | view/add/edit/delete |
| **ProjectType** | `project_type` | list/create/read/update/delete | view/add/edit/delete |
| **Phase** | `phase` | list/create/read/update/delete | view/add/edit/delete |
| **Blocks** | `projects` | list/read + `DELETE /blocks/{id}` | view (write folded into Phase create/update); delete gated `require_permission("projects","delete")` and returns 409 if referenced by an active `Category` (Q7) |
| **Lots** | `projects` | read (nested in blocks) + `DELETE /lots/{id}` | view; delete gated `require_permission("projects","delete")` and returns 409 if referenced by an active `Category` (Q7) |
| **Category** | `category` (Q11) | list/create/read/update/delete | view/add/edit/delete |
| **Model** | `models` | list/create/read/update/delete | view/add/edit/delete |
| **ModelTypes** | `model_types` | list/create/read/update/delete | view/add/edit/delete |
| **Owner** | `owner` | list/create/read/update/delete | view/add/edit/delete |
| **EmployeeProjects** | `emp_project` | list/create/read/update/unassign/delete | view/add/edit/delete |
| **EmpTask** | `emp_task` (Q11) | list/create/read/update/delete | view/add/edit/delete |
| **EmpTask approve/deny** | `emp_project` (Q9) | `POST /emp-tasks/{id}/approve`, `POST /emp-tasks/{id}/deny` | edit (gated `require_permission("emp_project","edit")`) |
| **Role (UserType)** | `administration` | `GET /rbac/roles`, `POST /rbac/roles`, `PATCH /rbac/roles/{id}`, `DELETE /rbac/roles/{id}` | view/add/edit/delete |
| **User (admin)** | `administration` | `GET/POST/PATCH/DELETE /admin/users[/...]` (separate from self-service `/users/me`) | view/add/edit/delete |
| **Dashboard** | `emp_list` (or a `dashboard` read) | `GET /dashboard` | view (any authenticated user, like legacy) |

**Owner create/update payloads (Q8, corrected):** take `lot_no` / `block` as **strings**
(denormalised display labels), NOT `lot_id`/`block_id` FKs. The authoritative
owner↔lot link is `Owner` → `Category` → `Lots` (via `Category.owner_id` +
`Category.lot_id`); ownership queries must read `Category`, not `Owner`. See §1.3 Owner
note and §4 Q8.
update by id, any field including `user_type`) is **split** into:
- self-service `PATCH /users/me` (Phase 0 already exists, `UserUpdateMe` excludes
  role) — untouched, safe.
- admin `PATCH /admin/users/{id}` — a schema that **explicitly omits `role_id`**.
- admin `POST /admin/users/{id}/role` — the **only** endpoint that sets a role,
  gated by `require_permission("administration", "edit")`.

**Collapse of legacy duplicates:** `api/subdivision/update` and
`api/project/subdivision/update` → one `PATCH /subdivisions/{id}`.
`ModelControllersController` + `ModelTypeController` → one `model_types` router.
`bulk_update`/`bulk_update_v2` → one `POST /employees/bulk-flags` (gated, server-
authoritative, no raw DQL over arbitrary user ids by non-admins).

---

## 3. The role-escalation fix

**Mechanism (best fit for Phase 0 RBAC): separate admin-only endpoint + role field
excluded from all self/other update schemas.**

1. **`UserUpdateMe` (self) and `UserAdminUpdate` (admin) schemas both omit
   `role_id`.** There is no `role`/`user_type` field anywhere in a user-update
   request body. Pydantic rejects any stray `role_id`/`user_type` key (or it is
   ignored via `model_dump(exclude_unset=True)`). This closes the legacy
   `UsersController::updateUser` vector by construction — the caller literally
   cannot express "set my role to admin" in the request.

2. **Role changes go through `POST /admin/users/{id}/role`** (or
   `PATCH /rbac/roles/{id}/members`), gated by
   `Depends(require_permission("administration", "edit"))`. It accepts only
   `{ "role_code": "..." }` (or `role_id`), validated against existing `Role` rows,
   and refuses to act on `is_system` roles (SADM/ADM) unless the caller is a
   superuser. No self-targeting special case needed because a non-admin simply
   lacks the permission.

3. **`revalidate-session` is removed** (it minted a JWT for any `user_id`). Phase 0
   already implements proper refresh-token rotation (`/logout`,
   `/login/refresh-token`), so session renewal uses the refresh token, not a bare
   user id. No replacement endpoint takes a `user_id` from the body.

4. **`/signup` (Q12, final decision):** the inherited `POST /api/v1/users/signup`
   endpoint is **gated behind `Depends(require_permission("administration", "add"))`** —
   admin-only, not publicly reachable, and not removed entirely. The `UserRegister`
   schema already cannot set a role, so the escalation vector is gone; the endpoint now
   requires an authenticated admin token. It is removed from `route_policy.PUBLIC_ROUTES`
   (the Phase 0 FIXME is resolved). Alternative admin user provisioning also exists via
   `POST /admin/users`.

5. **Role (UserType) CRUD is `Role` CRUD on `app/rbac/models.py`.** Creating a role
   writes `Role` + `RolePermission` rows. Soft "delete" = `is_active = false`
   (never hard-delete, because legacy hard-delete orphaned users → HTTP 500 on
   login). A system role (`is_system=True`: SADM/ADM/HR/PAY) **cannot** be deleted
   or have its permissions zeroed by CRUD. Assigning a role to a user is the
   admin-only action in (2), never part of user update.

6. **Server-authoritative actor:** all writes record `updated_by`/audit from
   `CurrentUser`, never a client-supplied field. (Sets up the Phase 3
   actor-spoofing test pattern early.)

This satisfies `b1.testsRequired[1]`: "Test confirming a user cannot escalate
their own role" — see §5.

---

## 4. Decisions (all 12 finalized)

These replace the prior open-questions list. Numbering Q1–Q12 is retained for
traceability against the earlier draft and against the sections above.

1. **`EmployeeRecords.age` — DROP.** The column is removed entirely. Age is computed
   from `birthdate` on read (in the schema/serializer layer), never persisted. (§1.1
   no longer lists `age`.)
2. **Enums — `employee_status` only.** Introduce a `str` Enum (`EmployeeStatusEnum`)
   with values taken from the actual legacy literals: `ACTIVE="Active"`,
   `RESIGNED="Resigned"`, `TERMINATED="Terminated"`, `ON_LEAVE="On Leave"`. Stored as
   VARCHAR. `gender` and `civil_status` stay plain `String` (not enums) for now. (§1.1)
3. **`EmployeeRecords.position` — real FK.** `position_id: UUID FK → Position.id`,
   `nullable=True`. The free-text `position` string field is removed entirely. Legacy
   free-text position values must be resolved/created against the new `Position` table
   during the Phase 6 ETL (see §6). (§1.1, §6)
4. **Division delete — 409, no cascade/orphan.** Deleting a Division that has any active
   (`is_deleted = false`) Department children returns **409 Conflict** and does NOT
   cascade or orphan them. No re-parenting logic. (§1.2)
5. **Denormalised counts — drop from write path.** `Subdivision.total_lots`,
   `Phase.total_blocks`, `Phase.total_lots`, `Blocks.total_lots` are removed from the
   Create/Update schemas. Values are derived via `COUNT()` queries in list/read
   serializers. If keeping a nullable column for migration fidelity is simpler, it may
   remain but the API must never write to it — only read paths compute it live. (§1.2,
   §1.3)
6. **`ProjectType` — CREATE (reverses original "skip").** New `ProjectType` table
   (id UUID PK, `code` String(32) unique, `name` String(255), `description`
   String(1024), `is_deleted`, `deleted_at`). `Project.project_type_id` becomes a real,
   populated FK with basic CRUD under the `project_type` module. (§1.3, §2)
7. **Blocks/Lots — add `is_deleted` + `deleted_at`.** Both tables gain soft-delete
   (legacy had none). Delete endpoints for either return **409 Conflict** if still
   referenced by an active (`is_deleted = false`) `Category`; no hard delete once
   referenced. (§1.3)
8. **`Owner.lot_no`/`block` — keep as denormalised text (CORRECTED from prior FK plan).**
   Per legacy entity mappings (`Owner` has **no** FK to `Lots`/`Blocks`; only `lot_no`/
   `block` strings; the real link is `Owner` → `Category` → `Lots` via
   `Category.owner_id` + `Category.lots`), **`Owner.lot_id` / `Owner.block_id` FKs are
   NOT added** — they would duplicate `Category`'s authoritative links. `Owner.lot_no`/
   `block` remain `String` columns (display convenience). Ownership queries go through
   `Category`. (§1.3, §2, §6)
9. **EmpTask approve/deny — gate under `emp_project`/`edit`.** Both actions use
   `Depends(require_permission("emp_project", "edit"))`. No new permission module in
   Phase 1. (§1.4, §2)
10. **Dashboard `dtr_records_daily_count` — distinct employees + Asia/Manila tz.** Count
    **DISTINCT employees** with ≥1 worker log today (not raw log rows), using an
    explicit Asia/Manila timezone boundary for "today". Finalized, not open. (§1.6)
11. **RBAC seed — add `category` + `emp_task` modules.** Two new module codes added to
    `app/rbac/seed.py` `SUBMODULES`. Category CRUD gates under `category` (not folded
    into `projects`); EmpTask non-approval CRUD gates under `emp_task`. Q9 already
    settles that approve/deny specifically stays under `emp_project`/`edit`. (§2, §6)
12. **`/signup` — admin-gated.** `POST /api/v1/users/signup` is gated behind
    `Depends(require_permission("administration", "add"))` — admin-only, not public,
    not removed. Removed from `route_policy.PUBLIC_ROUTES`. (§3)

---

## 5. Test plan (maps to `b1.testsRequired`)

### Test set A — CRUD tests per resource
For **every** resource in §2 (EmployeeRecords, EmployeeAdditionalRecords,
EmployeeAttachments, Division, Department, Subdivision, Position, Project, Phase,
Blocks, Lots, Category, Model, ModelTypes, Owner, EmployeeProjects, EmpTask, Role),
add pytest in `backend/tests/<package>/test_*.py` covering:

- **create** — valid payload returns 201 + persisted row; duplicate unique key
  (employee_code, role code, model_types code, etc.) returns 409.
- **read (list)** — returns only `is_deleted = false` rows (soft-delete isolation).
- **read (by id)** — 404 for unknown id; 200 for existing.
- **update** — PATCH changes the column; unknown id → 404; partial update does
  **not** null unrelated columns (fixes legacy `date_hired` null-on-omit bug).
- **soft-delete** — `DELETE` sets `is_deleted = true` and `deleted_at` is populated;
  the row disappears from list endpoints; a direct DB read confirms `is_deleted =
  true` (NOT physically removed). For `Role`, "delete" sets `is_active = false`
  and the role stays resolvable (no user orphaning / login 500).
- **permission gate** — a token without the required module/action gets 403; a
  superuser or correctly-permissioned role gets 200. (Reuses the Phase 0
  `test_route_protection` pattern so the route-protection suite also stays green.)
- **route-protection regression** — `tests/rbac/test_route_protection.py` must still
  pass: every new route is authenticated or explicitly public; no stale
  `PUBLIC_ROUTES` entries.

### Test set B — user cannot escalate their own role
`backend/tests/rbac/test_role_escalation.py` (or under `tests/user`):

1. **Self-update excludes role.** A low-privilege user (`SUR`) calls
   `PATCH /api/v1/users/me` with body `{"role_id": "<admin_role_id>"}` (or
   `{"user_type": "..."}`). Assert 200 but the persisted `User.role_id` is
   **unchanged** (schema omits the field; stray key ignored).
2. **Admin update excludes role.** `PATCH /api/v1/admin/users/{id}` with a
   `role_id` in the body asserts the field is ignored / rejected (schema omits it).
3. **Role change requires the dedicated endpoint + permission.** Calling
   `POST /api/v1/admin/users/{self_id}/role` with body `{"role_code":"SADM"}` as a
   non-admin token → 403. As an admin → 200 and `User.role_id` flips.
4. **No self-promotion via the dedicated endpoint.** Even with the permission,
   assert a non-superuser cannot set `is_system` roles (SADM/ADM) — 403.
5. **No `revalidate-session` escape.** Assert there is no route that mints a token
   from a bare `user_id` (endpoint removed); login refresh requires a valid refresh
   token.
6. **Role (UserType) soft-delete safety.** Deleting a role sets `is_active=false`;
   a user holding it can still log in (role resolves, permissions empty/denied by
   design) — no 500.

### Test set A2 — Blocks/Lots DELETE endpoints + soft-deleted-Category guard (Point 1 & 2)

These extend the generic CRUD `soft-delete` bullet with the explicit,
named cases for `DELETE /blocks/{id}` and `DELETE /lots/{id}` (routes added in §2,
gated `require_permission("projects","delete")`). Put in
`backend/tests/manpower/test_blocks_lots_delete.py`.

**A2.1 Permission gate (Point 2).** Calling `DELETE /blocks/{id}` / `DELETE /lots/{id}`
with a token lacking `projects`/`delete` → **403**. With a superuser or
`projects`/`delete`-permissioned role → proceeds. (Reuses the Phase 0 route-protection
pattern.)

**A2.2 Success case (Point 2).** On an unreferenced Block/Lot, `DELETE` returns
200/204; `is_deleted = true` and `deleted_at` populated; row disappears from
`GET /blocks` / `GET /lots` list (which filters `is_deleted = false`); direct DB read
confirms soft-delete, not physical removal.

**A2.3 Baseline — zero references (Point 1).** A Block/Lot referenced by **no**
Category at all → `DELETE` succeeds immediately (200/204). Documents the happy path
before the guard logic is exercised.

**A2.4 Soft-deleted-Category exception (Point 1 — the core regression test).**
1. Create a `Block` (and separately a `Lot`), attach it to a **Category** (`is_deleted = false`).
2. `DELETE /blocks/{id}` (resp. `/lots/{id}`) → assert **409 Conflict** (active Category
   reference blocks deletion).
3. Soft-delete **that** Category (`is_deleted = true`, `deleted_at` set) via the
   Category delete endpoint.
4. `DELETE /blocks/{id}` (resp. `/lots/{id}`) again → assert **200/204** (now succeeds,
   because no **ACTIVE** Category references it).
5. **Explicit assertion:** the test must assert the guard query excludes soft-deleted
   Category rows — i.e. the difference between steps 2 and 4 is solely the
   `Category.is_deleted` flag, not the passage of time or any other state. Implemented
   via a service-level assertion that the guard is `WHERE (blocks_id|lot_id) = :id AND
   is_deleted = false` (not a bare FK-existence check). This proves a Block/Lot
   referenced only by a soft-deleted Category is deletable, not blocked forever.

> **Note:** A2.4 is the HTTP-endpoint expression of the §1.3 Q7 guard. The same
> scenario is additionally covered at the service layer so the guard's SQL predicate is
> asserted directly (not just "delete eventually works").

### Test set C — Owner/Category/Lots relationship contract (Point 3)

`backend/tests/org/test_owner_category_lots_contract.py`. Asserts the **corrected**
relationship shape (Owner → Category → Lots, per §4 Q8 / §1.3 Owner note), and acts as
a regression guard so the removed `Owner.lot_id`/`block_id` FKs are never silently
re-added.

**C.1 Category-mediated ownership resolves.** Create a `Category` with both
`owner_id` (→ Owner) and `lot_id` (→ Lots) set. Then look up "who owns Lot X" **via the
Category record** (e.g. read `Category` where `lot_id = X`, resolve `Category.owner`).
Assert it returns the correct `Owner`. This pins the authoritative link to `Category`,
not `Owner`.

**C.2 Owner has NO lot_id/block_id FK fields (regression).** Assert the `Owner`
SQLModel class / Pydantic schemas / API response shape do **not** contain `lot_id` or
`block_id` fields. The test fails loudly if someone re-adds them without understanding
why they were removed. (Implementation: import `Owner` model + `OwnerCreate`/`OwnerPublic`
schemas and assert `'lot_id' not in <fields>` / `'block_id' not in <fields>`.)

**C.3 Non-authoritative display labels tolerated.** Assert `Owner.lot_no` /
`Owner.block` (the retained `String` columns) may hold values that **differ** from the
`Category`'s actually-linked Lot/Block without raising an error or constraint violation.
This documents that those strings are denormalised display labels, not enforced-consistent
data. (Create an Owner with `lot_no="X"` while its related Category links Lot `Y`; assert
both persist without error.) They are intentionally NOT kept in sync by the API.

### Test set D — Indexing & Constraints (Point 4 / §7)

`backend/tests/foundation/test_indexes_constraints.py` (or a migration-verification
module aligned with the project's existing Alembic test pattern). Covers §7.1 composite
indexes and §7.4 unique constraints.

**D.1 Composite indexes exist post-migration (§7.1).** After migrations run, query the
Postgres system catalogs (`pg_indexes` / `information_schema.statistics`) for each
composite index enumerated in §7.1 and assert it exists with the expected column set:
- `EmployeeRecords`: `(division_id, is_deleted)`, `(department_id, is_deleted)`,
  `(employee_status, is_deleted)`.
- `Category`: `(project_id, is_deleted)`, `(phase_id, is_deleted)`.
- `Subdivision`: `(project_id, is_deleted)`.
- `Phase`: `(subdivision_id, is_deleted)`.
- `Blocks`: `(phase_id, is_deleted)`.
- `Lots`: `(blocks_id, is_deleted)`.
- `EmployeeProjects`: `(project_id, is_deleted)`, `(employee_id, is_deleted)`.
- `EmpTask`: `(emp_project_id, is_deleted)`.
- `Project`: `(subdivision_id, is_deleted)`, `(project_type_id, is_deleted)`.
- `Department`: `(division_id, is_deleted)`.

If the project has an existing Alembic migration-test harness, use it; otherwise this is
a documented post-migration check (run once against a migrated test DB).

**D.2 Unique-constraint violation → mapped 409, not 500 (§7.4).** Per unique field in
§7.4, attempt to create a duplicate and assert the **HTTP 409** response (not an
unhandled 500) with the Phase 0 `ErrorBody` shape (`success=false`, `detail` message,
structured `error`). Cases:
- `EmployeeRecords.employee_code` duplicate → 409.
- `EmployeeAdditionalRecords.employee_id` (second annex for same employee) → 409.
- `Category.lot_id` duplicate (two Categories claiming the same Lot) → 409.
- `Division.code` / `Department.code` / `Subdivision.subdivision_code` / `Position.code`
  / `Project.code` / `Phase.code` / `ModelTypes.code` / `ProjectType.code` duplicate → 409.
- (If added) `User.username` duplicate → 409.

**D.3 Concurrency / DB-constraint-is-the-backstop (§7.4).** If the test harness can fire
near-simultaneous requests, assert that two `POST` creates with the **same unique key**
result in exactly **one 200/201 and one 409** — proving the DB constraint (not just
app-level validation, which races) is the real backstop. If true concurrency is not
practical in the suite, document this as a **manual / load-test verification item** here
(rather than silently omitting it): "Run two parallel inserts with identical
   `employee_code` under load; expect exactly one success and one 409; the 500-rate must be
   zero." Mark it `skip`/`xfail` with that rationale in the automated suite.

### §5 ↔ `b1.testsRequired` traceability

`docs/roadmap/backend-phases.json` `b1.testsRequired` has two items; both remain fully
covered by the (now-expanded) §5, with no orphaned requirements:

| `b1.testsRequired` item | Covered by |
|---|---|
| **"CRUD tests per resource (create/read/update/soft-delete)"** | Test set A (generic CRUD + soft-delete bullet) for all 18 resources, **plus** the explicitly-added Point 1/2 cases: A2.2 success + A2.3 zero-reference baseline + A2.4 soft-deleted-Category guard for `Blocks`/`Lots` soft-delete-through-`DELETE` endpoints. |
| **"Test confirming a user cannot escalate their own role"** | Test set B (B.1 self-update excludes role, B.2 admin-update excludes role, B.3 dedicated endpoint + 403, B.4 no system-role self-promotion, B.5 no revalidate-session escape, B.6 role soft-delete safety). |

Point-specific additions map as: **Point 1 → A2.3 + A2.4**; **Point 2 → A2.1 + A2.2 +
A2.4**; **Point 3 → Test set C**; **Point 4 → Test set D**. All `b1` items are traceable;
none are orphaned.

---

## 6. Implementation notes (non-binding, for the executor)

- Layered per resource: `models.py` (SQLModel tables) + `schemas.py` (Create/Read/
  Update/Public) + `routes.py` (thin, `require_permission` deps) + `services.py`
  (transactions, soft-delete, cascade rules) + `selectors.py` (read helpers).
  Follow `app/item/*` and `app/rbac/*` exactly.
- Register routers in `app/api.py`; add the new module codes to
  `app/rbac/seed.py` `SUBMODULES` (Q11: `category`, `emp_task`, and Q6: `project_type`)
  and re-run seed idempotently.
- Alembic: one migration per logical group (employee, org, manpower, rbac-role-
  crud, project_type). UUID PKs + `is_deleted`/`deleted_at` on all mutable tables
  (including the newly soft-delete-enabled `Blocks` and `Lots`, Q7).
- Audit: all writes go through the Phase 0 audit middleware; `AUDIT_REDACTED_FIELDS`
  covers `password`, `hashed_password`, `reset_token`, and the 201-file government
  IDs (`sss_number`, `tin_number`, etc.) so PII is never logged in clear.
- Phase 6 ETL must map legacy `archived`/`isArchived`/`removed` → `is_deleted`, and
  legacy table names (e.g. `dtradjutments`, `sssconfig`) → clean names per §1; the
  mapping table is the deliverable of Phase 6, but the clean names are fixed here.
  - **Position (Q3):** legacy free-text `EmployeeRecords.position` values must be
    resolved against / created as rows in the new `Position` table during migration;
    set `position_id` accordingly (unknown values → new Position rows or a flagged
    review bucket).
   - **Owner (Q8, corrected):** legacy `Owner.lot_no` / `block` text values are copied
     verbatim into the denormalised `Owner.lot_no` / `Owner.block` `String` columns — no
     FK resolution is needed (so there are no unresolvable-row failures to flag). The
     real owner↔lot association is rebuilt through `Category` (`Category.owner_id` +
     `Category.lot_id`); the ETL may optionally *enrich* `Category.lot_id` /
     `Category.owner_id` from these strings, but the strings themselves stay on `Owner`
     for legacy fidelity.
  - **ProjectType (Q6):** `Project.project_type_id` is populated from the new
    `ProjectType` table; migrate any legacy `project_type` references or leave nullable
    where absent.
- Indexing & constraints from §7 must be declared as DB-level constructs via
  SQLModel/Alembic (composite indexes on `is_deleted` + FK filter columns, single-
  column indexes on frequently-filtered fields, and unique constraints — not just
  app-level validation, which races under concurrency).

---

## 7. Indexing & Constraints

All indexes/constraints below are declared at the DB level via SQLModel field options
/ `Index`/`UniqueConstraint` and realised in Alembic — never app-level-only, which
races under concurrent requests.

### 7.1 Composite indexes pairing `is_deleted` with the FK it is filtered alongside

List endpoints filter by a FK **plus** `is_deleted = false` together, so a lone
`is_deleted` boolean index is useless. Declare composite indexes:

- **EmployeeRecords**: `(division_id, is_deleted)`, `(department_id, is_deleted)`,
  `(employee_status, is_deleted)`.
- **Category**: `(project_id, is_deleted)`, `(phase_id, is_deleted)`.
- **Subdivision**: `(project_id, is_deleted)` (project listing filters by subdivision).
- **Phase**: `(subdivision_id, is_deleted)`.
- **Blocks**: `(phase_id, is_deleted)`.
- **Lots**: `(blocks_id, is_deleted)`.
- **EmployeeProjects**: `(project_id, is_deleted)`, `(employee_id, is_deleted)`.
- **EmpTask**: `(emp_project_id, is_deleted)`.
- **Project**: `(subdivision_id, is_deleted)`, `(project_type_id, is_deleted)`.
- **Department**: `(division_id, is_deleted)`.
- **Division**: its list filters on `is_deleted` alone (no FK list-filter), so the
  standalone `is_deleted` index (from §1 convention) suffices — no composite needed.
- **Model, ModelTypes, Owner, Position, ProjectType**: list endpoints filter on
  `is_deleted` alone (keyed by unique `code`), so the standalone `is_deleted` index
  suffices — no composite needed.

> **§7.1 coverage confirmation:** every resource whose list endpoint filters by a FK +
> `is_deleted` together (per §2) is covered above. Resources that filter on `is_deleted`
> alone are served by the standalone `is_deleted` index declared in §1. The reviewer
> TODO has been resolved; no further composite indexes are outstanding.

### 7.2 Additional single-column indexes for frequently-filtered fields

Not covered by FK indexes already (FK columns get their own index automatically per
§1 convention, but call out explicitly in 7.3):

- **EmployeeRecords.position_id** — indexed (frequent filter by position).
- **EmployeeRecords.employee_status** — indexed (queried as a literal in 9 places;
  pairs with 7.1's composite as well).

### 7.3 FK columns used in joins must be indexed (not just the referenced PK side)

SQLModel/SQLAlchemy create an index on the FK column by default, but confirm
explicitly for the high-traffic join keys:

- **Category.project_id**, **Category.phase_id**, **Category.blocks_id**,
  **Category.lot_id**, **Category.owner_id** — all indexed.
- **EmployeeRecords.division_id**, **EmployeeRecords.department_id**,
  **EmployeeRecords.position_id**, **EmployeeRecords.user_id**,
  **EmployeeRecords.affiliated_company_id** — indexed.
- **Project.subdivision_id**, **Project.project_type_id** — indexed.
- **Phase.subdivision_id** — indexed.
- **Blocks.phase_id** — indexed.
- **Lots.blocks_id** — indexed.
- **EmployeeProjects.employee_id**, **EmployeeProjects.project_id** — indexed.
- **EmpTask.emp_project_id** — indexed.
- **Division.director_id**, **Department.division_id**, **Department.manager_id** —
  indexed.
- **EmployeeAdditionalRecords.employee_id**, **EmployeeAttachments.employee_id** —
  indexed.
- **Owner** has no FK join columns (per Q8 it keeps only `lot_no`/`block` denormalised
  strings), so no FK index is required; `is_deleted` and `code` (if any) are indexed.

### 7.4 DB-level unique constraints (not app-level-only)

Each field marked `unique=True` across §1 must be a real DB constraint:

- **EmployeeRecords.employee_code** — `UniqueConstraint`.
- **EmployeeAdditionalRecords.employee_id** — `UniqueConstraint` (one annex per
  employee).
- **Category.lot_id** — `UniqueConstraint` (a lot maps to at most one category;
  legacy OneToOne).
- **Division.code**, **Department.code**, **Subdivision.subdivision_code**,
  **Position.code**, **Project.code**, **Phase.code**, **ModelTypes.code**,
  **ProjectType.code**, **Owner** has no natural unique key — all `code` columns
  declared `unique=True` in §1 are DB-enforced `UniqueConstraint`s.
- **User.username** (if added per §1.5) — `UniqueConstraint`.
- **Role.code** / **Module.code** — already unique in Phase 0; unchanged.

Enforcement note: unique violations must raise a mapped 409 (not a 500) in services,
and the DB constraint is the backstop against concurrent inserts.

### 7.5 Future consideration (no Phase 1 action)

If any field inside `EmployeeAdditionalRecords`' JSON columns is ever queried/filtered
directly in a later phase, a **GIN index** should be added on that JSONB column at that
time. This is flagged for awareness only and is **not** a Phase 1 task.
