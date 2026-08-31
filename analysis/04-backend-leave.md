# Backend Leave & Holiday Business Logic — Analysis

**Project:** `/mnt/f/laragon/www/wchhris-api` (Symfony 7.0, PHP >= 8.2, Doctrine ORM 3.1, LexikJWT)
**Scope:** LEAVE (requests, policies, balances) and HOLIDAY (config, yearly instances) only. Attendance / DTR / overtime are covered in `03-backend-attendance.md`; payroll math in `02-backend-payroll.md`.
**Mode:** Read-only static analysis. No source file was modified.

**Files analysed**

| Layer | Files |
|---|---|
| Controllers | `LeaveRequestController.php`, `LeavePolicyController.php`, `EmployeeLeavesController.php`, `SelectedEmployeeLeavesController.php`, `HolidayConfigController.php`, `YearlyHolidayController.php` |
| Entities | `LeaveRequest.php`, `LeavePolicy.php`, `YearlyEmployeeLeave.php`, `SelectedEmployeeLeaves.php`, `HolidayConfig.php`, `YearlyHoliday.php` |
| Repositories | `LeaveRequestRepository`, `LeavePolicyRepository`, `YearlyEmployeeLeaveRepository`, `SelectedEmployeeLeavesRepository`, `HolidayConfigRepository`, `YearlyHolidayRepository` |
| Supporting | `config/packages/security.yaml`, `config/routes.yaml`, `src/Service/UserAccessValidation.php`, `src/Service/NotificationService.php`, `src/Entity/SubModules.php` |

---

## 0. Executive Findings (read this first)

1. **Leave has ZERO payroll effect.** A repo-wide search for `leave` outside the leave module returns only RBAC permission flags. `PayrollGenerationController`, `PayrollReportsController`, `PayslipController`, `DTRReportController`, `CheckEmpDtrController`, `EmployeePayrollProfileController`, `EmployeePayroll` and `EmployeePayrollProfile` contain **no reference to `LeaveRequest`, `LeavePolicy`, `YearlyEmployeeLeave` or `SelectedEmployeeLeaves`**. Approved paid leave does **not** credit pay, and unpaid leave does **not** trigger any deduction. "No-work-no-pay" happens only implicitly, because the absent day produces no DTR record.
2. **Holiday pay is NOT implemented in payroll.** `HolidayConfig.multiplier_regular` / `multiplier_overtime` are stored and returned by the API but are **never read by any calculation**. The only occurrence of the string `holiday` outside the holiday module is the *unrelated* payroll field `sal_adj_4hrs_more_weekend_holiday` (`PayrollGenerationController.php:1136`), which is a manually-entered salary-adjustment amount, not a holiday-premium computation. **There is no function anywhere that answers "is date X a holiday?"** — holidays are a reference dataset for the UI calendar only.
3. **There is no "leave type" enum.** Leave types are pure data — rows in the `leave_policy` table. Nothing in code declares Vacation/Sick/Emergency/Maternity, and there is **no paid-vs-unpaid flag at all** (see §2.2).
4. **Three overlapping leave tables** (`yearly_employee_leave`, `selected_employee_leaves`, plus the vestigial many-to-many) are explained in §3.
5. **No authorization on any leave or holiday endpoint.** JWT authentication is enforced globally by `security.yaml`, but not a single route performs a role, department or ownership check. Any authenticated user can approve their own leave, edit anyone's balance, or delete holiday configs (§7).
6. **Two routes are unreachable / broken by construction:** `PUT /api/leave/request/update/{id}` (route-name collision) and `PUT /api/leave-policy/update-list` (unresolvable controller argument). See §8.1 and §8.2.

---

## 1. Global Routing & Security Context

`config/routes.yaml` loads `../src/Controller/` with `type: attribute` and no global prefix, so every path below is the literal URL.

`config/packages/security.yaml` access control:

```yaml
- { path: ^/api/login,                 roles: PUBLIC_ACCESS }
- { path: ^/api/forget_password,       roles: PUBLIC_ACCESS }
- { path: ^/api/validate_reset_token,  roles: PUBLIC_ACCESS }
- { path: ^/api/reset_password,        roles: PUBLIC_ACCESS }
- { path: ^/api,                       roles: IS_AUTHENTICATED_FULLY }
```

Firewall `api` = `pattern: ^/api`, `stateless: true`, `jwt: ~`, `provider: user_provider`.

**Consequence:** all 24 leave/holiday routes require only *a valid JWT*. Authorization granularity stops there.

### 1.1 Route-name generation rules used in this document
* `LeaveRequestController` and `HolidayConfigController` have **no class-level `#[Route]`** → paths are absolute, names are explicit.
* `EmployeeLeavesController` → class prefix `#[Route('/api/employee-leaves')]`, **no class-level name prefix**.
* `LeavePolicyController` → class prefix `#[Route('/api/leave-policy')]`, **no class name prefix and no method `name:` at all**. Symfony 7 `AttributeClassLoader::getDefaultRouteName()` (verified in `vendor/symfony/routing/Loader/AttributeClassLoader.php:236-247`) builds `strtolower(str_replace('\\','_', FQCN) . '_' . methodName)` → `app_controller_leavepolicycontroller_<method>`.
* `SelectedEmployeeLeavesController` → `#[Route('/api/selected-employee-leaves', name: 'selected_employee_leaves_')]` → names are `selected_employee_leaves_` + method name.
* `YearlyHolidayController` → `#[Route('/api/yearly-holiday', name: 'yearly_holiday_')]` → names are `yearly_holiday_` + method name.

### 1.2 RBAC flags that exist but are never enforced
`SubModules` defines permission arrays `leave_policy`, `emp_leaves`, `holiday_config`, `leave_request`, `leave_calendar`, and `MainModules` defines `emp_leaves`. These are returned at login (`LoginController.php:143,173-177,256,286-290`) and seeded by `SuperAdminController.php:348,402-406`, so **the frontend hides buttons** — but `UserAccessValidation::validateUserAccess()` has a `switch` covering only `subdivision, division, department, daily_time_record, phase, owner, models, model_types, emp_settings, shifts, employee_projects`. Leave and holiday submodules hit the `default:` branch and would return `400 Invalid Submodule` **if they were ever called** — and they never are. `LeaveRequestController` and `EmployeeLeavesController` inject `UserAccessValidation $validateAccess` into a private property and **never invoke it** (dead dependency).

---

## 2. Entity Model (exact fields)

### 2.1 `LeaveRequest` (`leave_request`) — the filed application
| Property | Column / type | Nullable | Notes |
|---|---|---|---|
| `id` | `INT` auto | no | PK |
| `emp_record` | `ManyToOne EmployeeRecords`, `inversedBy: 'leaveRequests'` | **`JoinColumn(nullable: false)`** | requester |
| `leave_policies` | `ManyToOne LeavePolicy`, `inversedBy: 'leaveRequests'` | **`JoinColumn(nullable: false)`** | the leave *type* |
| `reason` | `VARCHAR(255)` | yes | free text |
| `date_start` | `DATETIME_MUTABLE` (`\DateTime`) | no | stores time-of-day even though the domain is day-based |
| `date_end` | `DATETIME_MUTABLE` (`\DateTime`) | no | |
| `is_half_day` | `BOOLEAN` | no | |
| `document` | `VARCHAR(255)` | **no** | attachment reference — see §5.7 |
| `year` | `VARCHAR(255)` | no | **string**, not int; the balance bucket selector |
| `status` | `VARCHAR(255)` | no | **string column holding numeric codes** — see §5.1 |
| `updated_by` | `ManyToOne EmployeeRecords` | yes | approver/rejecter |
| `created_at` | `DATETIME_IMMUTABLE` | no | |
| `selected_leave` | `ManyToOne SelectedEmployeeLeaves`, `inversedBy: 'leaveRequests'` | yes | the *balance row* this request debits |
| `total_days_requested` | `FLOAT` | no | computed once at creation, frozen |

Redundancy: the request points at **both** `leave_policies` (the type) and `selected_leave` (the balance row, which itself points at a policy). Nothing enforces `selected_leave.leave_policy === leave_policies`; `create()` derives them from the same input so they agree, but `update()` (unreachable, §8.1) rewrites `leave_policies` **without** touching `selected_leave`, which would desynchronise them.

### 2.2 `LeavePolicy` (`leave_policy`) — the leave *type* definition
| Property | Column / type | Nullable | Purpose |
|---|---|---|---|
| `id` | `INT` auto | no | PK |
| `name` | `VARCHAR(255)` | **yes** (made nullable by `Version20250213092844`) | the leave type label, e.g. free text |
| `year` | `VARCHAR(255)` | **yes** (same migration) | policy vintage — a policy belongs to one calendar year |
| `description` | `VARCHAR(255)` | yes | |
| `days` | `FLOAT` | no | **the default annual entitlement** copied into a balance row |
| `calendar_color` | `VARCHAR(255)` | no | UI-only hex/colour for the leave calendar |
| `type` | `VARCHAR(255)` | yes | **free-text, never read by any backend logic** |
| `department` | `ManyToOne Department`, `inversedBy: 'leavePolicies'` | yes | `null` is explicitly documented in `create()` as "all departments" |
| `gender` | `VARCHAR(255)` | **yes** (same migration) | scope filter — **never applied server-side** |
| `marital` | `SMALLINT` | no | scope filter — **never applied server-side** |
| `increment_amount` | `INT` | no | accrual/seniority step — **never applied server-side** |
| `years_before_increment` | `INT` | no | tenure gate for the step — **never applied server-side** |
| `is_carried_over` | `BOOLEAN` | no | carry-over toggle — **never applied server-side** |

Inverse collections: `leaveRequests` (OneToMany), `selectedEmployeeLeaves` (OneToMany), and `yearlyEmployeeLeaves` — a `ManyToMany(targetEntity: YearlyEmployeeLeave, mappedBy: 'selected_leave_policies')` whose owning field **does not exist** on `YearlyEmployeeLeave`. See §3.4.

#### 2.2.1 Leave types — where they are defined
**Nowhere in code.** There is no enum, no PHP constant, no `AttendanceTypes`-style lookup, no fixture and no seeder for leave types. The full list of leave types is exactly *"whatever rows exist in `leave_policy`"*, created at runtime through `POST /api/leave-policy/create`. Static analysis therefore cannot enumerate them; the deployed database is the only source of truth.

#### 2.2.2 Paid vs unpaid
**The concept does not exist in the schema.** There is no `is_paid`, `with_pay`, `pay_rate` or `deduct` column on `LeavePolicy`, `SelectedEmployeeLeaves` or `LeaveRequest`. The nullable free-text `type` column is the only place a "With Pay"/"Without Pay" string *could* be stored by convention, but:
* no backend code ever calls `LeavePolicy::getType()` except to echo it in `GET /api/leave-policy/list`;
* payroll never loads leave at all (§0.1).

**Therefore the with-pay effect on payroll is: none.** Whether a leave is paid or unpaid changes nothing in the generated payroll. Both paid and unpaid leave behave identically as "no DTR record for that day", i.e. **everything is effectively no-work-no-pay**, and paid leave entitlements are only a counter that decrements.

#### 2.2.3 Entitlement / accrual semantics
* `days` is the **annual grant**. It is copied verbatim into `SelectedEmployeeLeaves.no_of_days` by `PUT /api/employee-leaves/update` (`EmployeeLeavesController.php:211`). That is the **only** place a policy entitlement is ever transferred into a balance.
* `increment_amount` + `years_before_increment` describe a seniority accrual ("after N years of service, add M days"). **No code reads either field.** There is no scheduled job, console command, cron, or Messenger handler in `src/` that touches leave. Accrual is therefore **not implemented**.
* **There is no monthly accrual.** Nothing prorates entitlement by month, cutoff or payroll period. Grant is a one-shot whole-year number.
* `is_carried_over` is hardcoded to `false` on create (`LeavePolicyController.php:93`) and is settable on update, but **nothing reads it**. See §3.3 for carry-over.
* `year` scopes a policy to a calendar year, so a "2025 Vacation Leave" and a "2026 Vacation Leave" are two separate `leave_policy` rows with two separate ids.

#### 2.2.4 Scope filters (gender / marital / department)
`gender` (string), `marital` (smallint) and `department` (FK) are declarative metadata only. **No query anywhere filters policies by the requesting employee's `EmployeeRecords.gender` or `EmployeeRecords.civil_status`.** `GET /api/leave-policy/list` returns *every* policy for *every* caller. Enforcement — if any — is entirely client-side, which means a crafted `POST /api/employee-leaves/update` can assign a maternity-scoped policy to a male employee, and `POST /api/leave/request/create` will happily let him consume it.

#### 2.2.5 Per-employee or per-type?
`LeavePolicy` is **per-type (and per-year, optionally per-department)** — it is a template, not an employee record. It becomes per-employee only when a `SelectedEmployeeLeaves` row materialises it against a `YearlyEmployeeLeave`.

### 2.3 `YearlyEmployeeLeave` (`yearly_employee_leave`) — the per-employee, per-year envelope
| Property | Column / type | Nullable |
|---|---|---|
| `id` | `INT` auto | no |
| `year` | `VARCHAR(255)` | no |
| `emp_record` | `ManyToOne EmployeeRecords`, `inversedBy: 'yearlyEmployeeLeaves'` | **`JoinColumn(nullable: false)`** |
| `selectedEmployeeLeaves` | `OneToMany SelectedEmployeeLeaves`, `mappedBy: 'employee_leave'` | inverse collection |

It holds **no numbers at all** — no entitlement, no balance, no used count. It is a pure grouping header: *(employee, year)*. **No unique constraint exists on `(emp_record, year)`**, so duplicates are possible (and §4.3 shows a bug that actively creates them).

### 2.4 `SelectedEmployeeLeaves` (`selected_employee_leaves`) — the actual balance ledger
| Property | Column / type | Nullable | Meaning |
|---|---|---|---|
| `id` | `INT` auto | no | PK |
| `leave_policy` | `ManyToOne LeavePolicy`, `inversedBy: 'selectedEmployeeLeaves'` | **yes** (no `JoinColumn(nullable:false)`) | which leave type |
| `employee_leave` | `ManyToOne YearlyEmployeeLeave`, `inversedBy: 'selectedEmployeeLeaves'` | **yes** | which (employee, year) |
| `no_of_days` | `FLOAT` | no | granted entitlement for the year |
| `used_days` | `FLOAT` | no | consumed |
| `carried_over_days` | `FLOAT` | no | days brought in from a prior year |
| `carry_over_policy` | `INT` | no | opaque integer flag; **never read** |
| `status` | `INT` | no | opaque integer flag; **never read** (always written as `0`) |
| `leaveRequests` | `OneToMany LeaveRequest`, `mappedBy: 'selected_leave'` | inverse | |

**The single balance formula in the entire codebase** (`LeaveRequestController.php:339`):

```php
$remaining_days = ($selected->getNoOfDays() + $selected->getCarriedOverDays()) - $selected->getUsedDays();
```

`leave_policy` and `employee_leave` being nullable means an orphan balance row (no type, no owner) is schema-legal, and `POST /api/selected-employee-leaves/create` can create exactly that.

### 2.5 `HolidayConfig` (`holiday_config`) — the holiday template
| Property | Column / type | Nullable | Notes |
|---|---|---|---|
| `id` | `INT` auto | no | |
| `name` | `VARCHAR(255)` | no | e.g. "New Year's Day" |
| `date` | `DATE_MUTABLE` | no | **a full `Y-m-d` including a year** — used as a month/day template |
| `multiplier_regular` | `FLOAT` | no | pay multiplier for regular hours — **never consumed** |
| `multiplier_overtime` | `FLOAT` | no | pay multiplier for OT hours — **never consumed** |
| `archived` | `BOOLEAN` | **yes** (added by `Version20250220051513`: `ADD archived TINYINT(1) DEFAULT NULL`) | soft-delete flag |
| `yearlyHolidays` | `OneToMany YearlyHoliday`, `mappedBy: 'holiday_config'` | inverse | |

### 2.6 `YearlyHoliday` (`yearly_holiday`) — the dated instance for one year
| Property | Column / type | Nullable |
|---|---|---|
| `id` | `INT` auto | no |
| `holiday_config` | `ManyToOne HolidayConfig`, `inversedBy: 'yearlyHolidays'` | **`JoinColumn(nullable: false)`** |
| `date` | `DATE_MUTABLE` | **yes** |
| `year` | `VARCHAR(255)` | no |
| `archived` | `BOOLEAN` | **yes** (added by `Version20250220051513`) |

---

## 3. `YearlyEmployeeLeave` vs `SelectedEmployeeLeaves` vs "EmployeeLeaves" — disambiguation

This is the most confusing part of the module, largely because of naming.

### 3.1 There is no `EmployeeLeaves` entity
`EmployeeLeavesController` is a **controller without a matching entity**. It is a façade that manipulates `YearlyEmployeeLeave` + `SelectedEmployeeLeaves` together. Do not look for an `employee_leaves` table — it does not exist. The name survives only in the URL prefix `/api/employee-leaves` and the RBAC flag `emp_leaves`.

### 3.2 The real shape is a classic header/detail pair

```
EmployeeRecords 1───* YearlyEmployeeLeave        (header: WHO + WHICH YEAR, zero numbers)
                              │ 1
                              │
                              *
                       SelectedEmployeeLeaves    (detail/ledger: one row per leave TYPE,
                              │ *                 holds no_of_days / used_days /
                              │                   carried_over_days)
                              │ 1
                        LeavePolicy              (template: the leave TYPE definition)
                              ▲
                              │
        LeaveRequest ─────────┘ (also FK'd directly to LeavePolicy — redundant)
             │
             └──── FK selected_leave ──► SelectedEmployeeLeaves  (the row that gets debited)
```

| Table | Grain | Owns numbers? | Written by |
|---|---|---|---|
| `leave_policy` | one row per *(leave type, year[, department])* | entitlement **template** (`days`) | `LeavePolicyController` |
| `yearly_employee_leave` | one row per *(employee, year)* | **no** | `EmployeeLeavesController::create_employee_leaves` / `::update_employee_leaves` |
| `selected_employee_leaves` | one row per *(employee, year, leave type)* | **yes — the authoritative balance** | `EmployeeLeavesController`, `SelectedEmployeeLeavesController`, and `LeaveRequestController::approveLeaveRequest` |

**Plain-English summary:** `YearlyEmployeeLeave` says *"employee #42 has a leave record for 2025"*. `SelectedEmployeeLeaves` says *"within that 2025 record, employee #42 was given 15 days of Vacation Leave, has used 3, and carried over 2"*. `LeavePolicy` says *"Vacation Leave 2025 is normally 15 days, coloured #22c55e, scoped to Female/married in dept X"*. They overlap only in that `SelectedEmployeeLeaves.no_of_days` is a **copied snapshot** of `LeavePolicy.days`, and once copied the two drift independently — editing a policy's `days` later never back-fills existing balances.

### 3.3 Carry-over: schema exists, logic does not
Three fields model carry-over — `LeavePolicy.is_carried_over` (bool), `SelectedEmployeeLeaves.carried_over_days` (float), `SelectedEmployeeLeaves.carry_over_policy` (int). Their behaviour:

* `carried_over_days` is **read exactly once**, in the approval balance formula (§2.4), where it inflates the available pool.
* `carried_over_days` is **written** only as a hardcoded `0` in `EmployeeLeavesController::update_employee_leaves` (line 213) and as `$data['carried_over_days'] ?? 0.0` in `::create_employee_leaves` (line 152) / `?? null` in `SelectedEmployeeLeavesController::create` (line 43) and `::update` (line 103).
* **No year-end rollover routine exists.** Nothing ever reads year *N*'s leftover `no_of_days - used_days` and writes it into year *N+1*'s `carried_over_days`. There is no console command, no cron entry, no Messenger handler, no scheduled task in `src/`.
* `is_carried_over` and `carry_over_policy` are **never read by any code path**.

**Net:** carry-over is manual data entry through `PUT /api/selected-employee-leaves/update/{id}` (an unauthenticated-by-role endpoint that lets any logged-in user type any number into anyone's `carried_over_days`).

### 3.4 The vestigial many-to-many (dormant bug)
`LeavePolicy.php:64`:
```php
#[ORM\ManyToMany(targetEntity: YearlyEmployeeLeave::class, mappedBy: 'selected_leave_policies')]
private Collection $yearlyEmployeeLeaves;
```
`YearlyEmployeeLeave` has **no** `selected_leave_policies` property and there is no join table. The matching `addYearlyEmployeeLeaf()` / `removeYearlyEmployeeLeaf()` helpers are commented out (`LeavePolicy.php:267-284`), confirming this is dead scaffolding from an earlier design where `YearlyEmployeeLeave` linked straight to policies, before `SelectedEmployeeLeaves` was introduced as an association entity carrying balance columns.

Why it does not crash at boot: Doctrine's `ClassMetadataFactory::validateRuntimeMetadata()` only verifies that `targetEntity` classes exist; the `mappedBy` field existence is checked by `doctrine:schema:validate`, not at runtime. The failure is **deferred to first access** of `LeavePolicy::getYearlyEmployeeLeaves()`, when the collection persister dereferences the non-existent owning mapping.

**This makes `GET /api/leave-policy/find/{id}` a likely hard 500** (§5.2), because it serialises the whole entity, and the Symfony `ObjectNormalizer` calls every public getter — including `getYearlyEmployeeLeaves()`.

### 3.5 Balance timing — when is `used_days` moved?
| Event | Effect on `used_days` |
|---|---|
| Filing (`POST /api/leave/request/create`) | **none** — no reservation, no pending hold, no balance check |
| Approval (`PUT /api/leave/request/approve/{id}` with `status == "1"`) | **`used_days += total_days_requested`** — the only decrement of available balance in the codebase |
| Rejection (`status == 2`) | none |
| Un-approval / status flipped 1 → 0 or 1 → 2 | **none — the used days are NOT returned** (§5.4) |
| Deletion (`DELETE /api/leave/request/delete/{id}`) | **none — the used days are NOT returned** (§5.6) |
| Actual consumption of the day / DTR posting | nothing — DTR is entirely unaware of leave |

So the model is **debit-on-approval**, with **no compensating credit on any reversal path**.

---

## 4. Controller: `LeaveRequestController`

No class-level `#[Route]` → every path is absolute. Constructor injects `EntityManagerInterface`, `UserPasswordHasherInterface` (unused), `JWTTokenManagerInterface` (unused), `AuditLog` (unused — **no leave action is ever audit-logged**), `UserAccessValidation` (unused), `LeaveRequestRepository`, `NotificationService`.

### Route inventory
| # | HTTP | Path | Route name | Method |
|---|---|---|---|---|
| 1 | GET | `/api/leave/request/list` | `app_leave_request_list` | `list()` |
| 2 | GET | `/api/leave/request/list-approved` | `app_leave_request_list_approved` | `approvedList()` |
| 3 | GET | `/api/leave/request/find/{id}` | `find_emp_leave_request` | `findEmployeeLeave()` |
| 4 | POST | `/api/leave/request/create` | `app_leave_request_create` | `create()` |
| 5 | GET | `/api/leave/request/find/{id}` | `app_leave_request_show` | `show()` — **shadowed, dead** |
| 6 | PUT | `/api/leave/request/update/{id}` | `app_leave_request_update` | `update()` — **clobbered, unreachable** |
| 7 | PUT | `/api/leave/request/approve/{id}` | `app_leave_request_update` | `approveLeaveRequest()` |
| 8 | DELETE | `/api/leave/request/delete/{id}` | `app_leave_request_delete` | `delete()` |

---

### 4.1 `GET /api/leave/request/list` — `app_leave_request_list` → `list()`
**Params:** none (no filtering, no pagination, no year scope).

**Logic:** `LeaveRequestRepository::findAll()`, then a projection loop.

**Response `200`:** a bare JSON **array** (not wrapped):
```jsonc
[{
  "id": 1,
  "emp_record": 42,
  "emp_name": "Cruz, Juan Cruz",          // lastName + ", " + firstName + " " + lastName  ← last name twice
  "selected_leave_id": 7,
  "selected_leave_policy_name": "Vacation Leave",
  "reason": "family matter",
  "date_start": "2025-03-04 00:00:00",     // 'Y-m-d H:i:s'
  "date_end": "2025-03-06 00:00:00",
  "is_half_day": false,
  "total_days_requested": 3,
  "document": "leave_doc.pdf",
  "year": "2025",
  "status": "1",                            // string
  "updated_by": 9,                          // or "" when null
  "updated_by_name": "Reyes, Ana Reyes",    // or ""
  "created_at": "2025-03-01 08:12:44",
  "total_days": 3                           // duplicate of total_days_requested
}]
```

**Defects**
* `emp_name` concatenates **last name twice** (`getLastName().", ".getFirstName()." ".getLastName()`), lines 55, 87, 118. Same for `updated_by_name`. This bug is copy-pasted into all three list endpoints.
* `getSelectedLeave()->getId()` and `->getLeavePolicy()->getName()` are dereferenced **without null checks**, but `selected_leave` is a nullable FK and `SelectedEmployeeLeaves.leave_policy` is also nullable → any legacy/orphan row makes the **whole endpoint return 500**.
* Unbounded `findAll()` — loads every leave request ever filed into memory, and lazily loads `EmployeeRecords` + `SelectedEmployeeLeaves` + `LeavePolicy` per row (**classic N+1**, 3 extra queries × N rows).
* No authorization → any authenticated employee reads the entire company's leave history including reasons.

### 4.2 `GET /api/leave/request/list-approved` — `app_leave_request_list_approved` → `approvedList()`
**Params:** none.
**Logic:** `findBy(['status' => 1])` — note the integer `1` compared against a `VARCHAR` column; Doctrine binds it as an integer, MySQL coerces, so it matches `'1'`. Identical projection and identical defects to §4.1.
**Response `200`:** same array shape.

### 4.3 `GET /api/leave/request/find/{id}` — `find_emp_leave_request` → `findEmployeeLeave()`
**Path param:** `{id}` — despite the generic name this is the **employee record id**, not the leave-request id.
**Params:** none besides the path.

**Logic:** `findBy(['emp_record' => $id])` → projection loop identical to §4.1 **plus** one extra key.

**Response `200`:** array of the §4.1 shape plus:
```jsonc
"count": 12   // count($leaveRequests) — repeated identically inside every element
```
Returns `[]` (200) when the employee has no requests — never 404.

### 4.4 `POST /api/leave/request/create` — `app_leave_request_create` → `create()`
**Body keys (exact):** `emp_record_id`, `year`, `leave_policies` (a LeavePolicy id), `reason`, `date_start`, `date_end`, `is_half_day`, `document`.

**Step-by-step**
1. `json_decode($request->getContent(), true)`.
2. `if (!$data['emp_record_id'])` → `404 {"message":"Employee not found!"}`. Uses direct array access, so a missing key raises a PHP warning and evaluates `null` → still 404.
3. `if (!$data['year'])` → `404 {"message":"Year not found!"}`.
4. `YearlyEmployeeLeave::findOneBy(['year' => $data['year'], 'emp_record' => $data['emp_record_id']])`; if none → `404 {"message":"Employee doesn't have leaves for this year."}`.
5. `SelectedEmployeeLeaves::findOneBy(['employee_leave' => $emp_yearly_leave, 'leave_policy' => $data['leave_policies']])`; if none → `404 {"message":"Employee Leave policy not found."}`.
6. Build `$dateStart` / `$dateEnd` as `new \DateTime(...)` and **normalise both to `setTime(0,0,0)`** — *these normalised objects are used only for the day count, not for persistence*.
7. `$interval = $dateStart->diff($dateEnd);`
8. Day count:
   ```php
   if ($data['is_half_day']) { $totalDays = 0.5; }
   else                      { $totalDays = $interval->days + 1; }   // inclusive of both ends
   ```
9. Construct `LeaveRequest`, setting `emp_record`, `leave_policies`, `reason`, **`date_start` / `date_end` from a *second*, non-normalised `new \DateTime($data[...])`**, `is_half_day` = `(int)$data['is_half_day']`, `document`, `year`, `status = 0`, `created_at = new \DateTimeImmutable()`, `selected_leave`, `total_days_requested`.
10. `persist()` + `flush()`.

**Response `201`:** `{"message":"Leave request created!"}` — **the created id is not returned**.
**Statuses:** `201`, `404` (×4). No `400` path.

**Validation that is MISSING (all of it)**
* **No overlap detection.** Nothing queries existing `LeaveRequest` rows for intersecting `date_start`/`date_end`. An employee can file ten fully-overlapping requests for the same day, and all ten can be approved (each debiting the balance again).
* **No balance sufficiency check at filing.** The pool is only tested at approval (§4.7), so a request for 400 days is accepted and sits Pending.
* **No duplicate prevention.** No unique key, no "already filed for these dates" check.
* **No past-date prevention.** `date_start` may be any date in the past; back-dating leave is unrestricted.
* **No `date_end >= date_start` check.** Because `DateInterval::$days` is **absolute**, a reversed range (`date_start` 2025-03-10, `date_end` 2025-03-04) yields `6 + 1 = 7` days rather than an error or a negative.
* **No weekend or holiday exclusion.** `$interval->days + 1` counts **calendar** days. A Friday→Monday leave is billed as **4 days**, consuming 2 days of balance for 2 non-working days. Given that `YearlyHoliday` data exists, its absence here is a notable functional gap.
* **No shift/rest-day awareness** — `Shifts` is never consulted.
* **No `status` check on `SelectedEmployeeLeaves`** — the `status` int column is ignored, so a "disabled" balance row is still usable.
* **No employee-active check** and **no ownership check** — `emp_record_id` is taken straight from the body, so any authenticated user can file leave *on behalf of anyone*.
* `document` is a **non-nullable** column read as `$data['document']` with no default → omitting it yields `null` → `setDocument(null)` against a `string` parameter → **TypeError → 500**.

**Half-day handling defect:** `is_half_day` short-circuits to a flat `0.5` **regardless of the date range**. A request with `is_half_day = true` spanning 2025-03-01 → 2025-03-31 stores `total_days_requested = 0.5` while `date_start`/`date_end` describe a month. Any consumer trusting the dates (e.g. a calendar view) will disagree with the balance ledger. There is also no half-day *slot* (AM/PM) field.

**Off-by-one analysis:** `+1` is *correct* for an inclusive single-day request (`diff` = 0 days → 1). It becomes wrong the moment weekends/holidays are involved (over-counts) and when combined with the `is_half_day` short-circuit (under-counts). Because `date_start`/`date_end` are persisted as `DATETIME` from the **raw** strings (step 9) rather than the midnight-normalised objects (step 6), a payload of `date_start: "2025-03-04 17:00"` stores 17:00 but is counted as a full day.

### 4.5 `GET /api/leave/request/find/{id}` — `app_leave_request_show` → `show()` **(DEAD CODE)**
Declared at line 202 with the **same path and method** as `find_emp_leave_request` (line 109) but a different name, so both routes register. Symfony's `UrlMatcher` returns the **first** match in registration order, and `AttributeClassLoader` walks methods in declaration order → `findEmployeeLeave()` (line 109) always wins. **`show()` is unreachable.**

Had it been reachable it would treat `{id}` as the **leave-request** id and return:
```jsonc
{"id":1,"emp_record":42,"leave_policies":3,"reason":"...","date_start":"Y-m-d H:i:s",
 "date_end":"Y-m-d H:i:s","is_half_day":false,"document":"...","year":"2025",
 "status":"0","created_at":"Y-m-d H:i:s"}
```
with `404 {"message":"Leave request not found!"}`. Note the two endpoints interpret `{id}` as **different entities** — a latent trap if the name collision is ever "fixed" by reordering.

### 4.6 `PUT /api/leave/request/update/{id}` — `app_leave_request_update` → `update()` **(UNREACHABLE)**
This method's route name `app_leave_request_update` is **reused** by `approveLeaveRequest()` at line 326. `RouteCollection::add()` (verified in `vendor/symfony/routing/RouteCollection.php`) begins with `unset($this->routes[$name], ...)` and re-adds — so **the later declaration completely evicts the earlier one**. `approveLeaveRequest` is declared after `update`, therefore the path `/api/leave/request/update/{id}` **is not in the route table at all → 404 for every caller.**

Intended body keys: `emp_record`, `leave_policies`, `reason`, `date_start`, `date_end`, `is_half_day`, `document`, `year`, `status`.

Even if routed, it is broken and dangerous:
* **`$leaveRequest->setDateStart($data['date_start'])` passes a raw string** into a parameter typed `\DateTimeInterface` → **TypeError → 500**. (`date_end` is correctly wrapped in `new \DateTime()`; `date_start` is not.)
* It lets the client set `status` **directly, bypassing the balance check and the `used_days` increment entirely** — a free approval with no ledger effect.
* It rewrites `leave_policies` without touching `selected_leave`, desynchronising the two (§2.1).
* `total_days_requested` is **not** recomputed after changing the dates, so the frozen day count silently becomes wrong.
* No `updated_by`, no audit, no transaction.

### 4.7 `PUT /api/leave/request/approve/{id}` — `app_leave_request_update` → `approveLeaveRequest()`
**Path param:** `{id}` = leave-request id.
**Body keys:** `status` (compared loosely to `"1"`), `user_id` (a **User** id, not an EmployeeRecords id).

**Step-by-step**
1. Decode body.
2. `find($id)`; if missing → `404 {"message":"Leave request not found!"}`.
3. `if ($data['status'] == "1")` — loose `==`, so integer `1`, string `"1"`, and `true` all enter the branch:
   1. `$days_leaved = $leaveRequest->getTotalDaysRequested();`
   2. `$remaining_days = (selected.no_of_days + selected.carried_over_days) - selected.used_days;`
   3. `if ($remaining_days < $days_leaved)` → `400 {"message":"Not Enough Leaves."}` (`HTTP_BAD_REQUEST`).
   4. `$used_days = selected.used_days + $days_leaved;`
   5. **Notifications (before the write is flushed):**
      * `Department::findOneBy(['code' => 'HRS'])` — **hardcoded department code**.
      * `NotificationService::createNotification($humanresDepartment->getDivision(), $humanresDepartment, "<Last> <First> Leave Request has been approved", "Leave Request of <Last> <First> is approved", new DateTime(), "DEP_ONLY")` — `DEP_ONLY` = notif type `1`, fans out to **every Active employee in the HRS department** (one `setNewNotification` INSERT per recipient, in a loop).
      * `createNotificationForSpecificUser($employee, <same title>, <same body>, new DateTime())` — notif type `"4"`, and this call performs its **own `flush()`** mid-request.
   6. `selected.setUsedDays($used_days);`
   7. `$this->entityManager->persist($leaveRequest);` — redundant, the entity is already managed.
4. `$leaveRequest->setStatus($data['status']);` — executed for **all** statuses, unvalidated.
5. `$leaveRequest->setUpdatedBy(EmployeeRecords::findOneBy(['user' => $data['user_id']]));`
6. `flush()`.

**Response `200`:** `{"message":"Leave request updated!"}`
**Statuses:** `200`, `400` (`Not Enough Leaves.`), `404`.

**Defects**
* **No idempotency guard — double-approval double-debits.** The method never checks the *current* status. Calling approve twice on the same request adds `total_days_requested` to `used_days` **again**, silently draining the balance. This is the single most damaging bug in the module.
* **No reversal.** Flipping an approved request to `0` or `2` skips the whole `if` block, so `used_days` is never credited back. Balances only ever go up.
* **Self-approval is possible.** No check that the approver differs from `emp_record`, no manager/HR role gate, no department check. `user_id` is **supplied by the client**, not derived from the JWT — so the audit trail (`updated_by`) is client-controlled and forgeable. If `user_id` matches nothing, `findOneBy` returns `null` and `updated_by` is silently set to `null` (the FK is nullable).
* **No status whitelist.** `status` is a `VARCHAR`; `setStatus("banana")` or `setStatus("99")` succeeds.
* **Hardcoded `'HRS'`.** If no `Department` with `code = 'HRS'` exists, `$humanresDepartment->getDivision()` is a **method call on null → 500**, and — critically — this happens *after* the balance branch was entered but *before* `setUsedDays`, so the request stays Pending. Conversely `createNotificationForSpecificUser` flushes internally, so a later failure can leave notifications committed without the approval.
* **No transaction.** The `used_days` update, the status update and the N notification INSERTs are not wrapped in `beginTransaction()`/`commit()`, and an inner `flush()` splits them across implicit transactions. A crash between them leaves an inconsistent ledger.
* **No re-validation that the balance row still belongs to the employee/year** — `selected_leave` was resolved at filing time and may since have been re-pointed or deleted.
* `NotificationService::createNotification` internally does `EmployeeRecords::find($senderEmployeeRecordId)` where `$senderEmployeeRecordId` is **already an entity object**, not an id (`NotificationService.php:36-38`) — a latent type bug on the approval path.
* The notification text says *"has been approved"* and is only produced for `status == 1`; **rejections notify nobody**.

**Multi-level approval:** none. `status` is a single scalar; there is no approver chain, no level column, no `approved_by_manager` / `approved_by_hr` split, no escalation. **Approval is single-step and role-less.**

### 4.8 `DELETE /api/leave/request/delete/{id}` — `app_leave_request_delete` → `delete()`
**Path param:** `{id}` = leave-request id. No body.
**Logic:** `find($id)` → if missing `404 {"message":"Leave request not found!"}`; else `remove()` + `flush()`.
**Response `200`:** `{"message":"Leave request deleted!"}`

**Defects**
* **Hard delete**, not a cancellation — there is no `status = 3 (Cancelled)` path and no soft-delete column, so the audit trail is destroyed.
* **Does not refund `used_days`.** Deleting an *approved* request permanently burns the balance.
* No authorization, no ownership check, no status check → any authenticated user can delete anyone's approved leave.
* No audit log despite `AuditLog` being injected.

### 4.9 Leave-request lifecycle summary
**Statuses — verified.** `status` is a `VARCHAR(255)` used as a numeric code. Confirmed values in code:
| Value | Meaning | Evidence |
|---|---|---|
| `0` | **Pending** | `create()` line 191: `setStatus(0)` — every new request starts here |
| `1` | **Approved** | `approvedList()` line 80 `findBy(['status' => 1])`; `approveLeaveRequest()` line 337 `$data['status'] == "1"` triggers the debit |
| `2` | **Rejected** | **inferred only** — no literal `2` appears anywhere in the backend. `setStatus($data['status'])` accepts any string, so `2` is a frontend convention the API neither defines nor validates |

There is **no Cancelled state** and **no re-application flow** (no link from a rejected request to a replacement; a re-application is simply a brand-new row, and nothing blocks re-filing identical dates).

**Date range vs single day:** always a range (`date_start`, `date_end`); a single-day leave is expressed as `date_start == date_end`, which yields `diff()->days = 0` → `+1` → `1.0` day. Correct.

**Attachments:** `document` is a single `VARCHAR(255)` on the request. **There is no upload endpoint in this controller** — no `UploadedFile` handling, no `$request->files`, no validation of extension/size/MIME, no storage path. The client must upload elsewhere (or supply an arbitrary string) and pass the reference. There is no per-policy "requires document" rule (e.g. sick leave medical certificate).

---

## 5. Controller: `LeavePolicyController`

**Class-level:** `#[Route('/api/leave-policy')]` — prefix only, **no `name:` prefix**, and **no method declares a `name:`**. All route names are auto-generated (§1.1).
Constructor injects `EntityManagerInterface`, `SerializerInterface` (**declared but never used**), `ValidatorInterface`.

> **Note on `ValidatorInterface`:** `$this->validator->validate($leavePolicy)` is called on create/update, but **`LeavePolicy` carries no `#[Assert\*]` constraints whatsoever**, so the validator always returns an empty list. The validation branch is decorative.

### Route inventory
| # | HTTP | Full path | Auto-generated route name | Method |
|---|---|---|---|---|
| 1 | GET | `/api/leave-policy/list` | `app_controller_leavepolicycontroller_index` | `index()` |
| 2 | GET | `/api/leave-policy/find/{id}` | `app_controller_leavepolicycontroller_show` | `show()` |
| 3 | POST | `/api/leave-policy/create` | `app_controller_leavepolicycontroller_create` | `create()` |
| 4 | PUT | `/api/leave-policy/update/{id}` | `app_controller_leavepolicycontroller_update` | `update()` |
| 5 | PUT | `/api/leave-policy/update-list` | `app_controller_leavepolicycontroller_updatelist` | `updateList()` — **broken** |
| 6 | DELETE | `/api/leave-policy/delete/{id}` | `app_controller_leavepolicycontroller_delete` | `delete()` |

### 5.1 `GET /api/leave-policy/list` → `index()`
**Params:** none — **no year filter, no department filter, no gender/marital filter, no archived filter** (there is no archived column on policies).
**Logic:** `LeavePolicyRepository::findAll()` + manual projection.
**Response `200`:** array
```jsonc
[{
  "id": 3, "name": "Vacation Leave", "year": "2025", "description": "…",
  "days": 15, "calendar_color": "#22c55e", "type": "With Pay",
  "gender": "Female", "marital": 1, "increment_amount": 1,
  "years_before_increment": 3, "is_carried_over": false,
  "department": "Human Resources"        // Department NAME (string) or null — NOT the id
}]
```
**Defect:** `department` is emitted as a **name**, but `create()`/`update()` expect an **id** — the response is not round-trippable, forcing the client to keep a separate department lookup. This is the endpoint the UI uses to render the leave-type picker, so §2.2.1's "types live in the DB" is realised here.

### 5.2 `GET /api/leave-policy/find/{id}` → `show()`
**Path param:** `{id}`.
**Logic:** `find($id)`; if missing → `404 {"message":"Leave Policy not found"}`; else **`return $this->json($leavePolicy);`** — serialises the raw entity rather than a projection.
**Response `200`:** serialiser-driven, therefore **inconsistent with §5.1** (different key set, relations expanded).

**Likely 500.** `$this->json()` uses the Serializer; `ObjectNormalizer` invokes every public getter, including:
* `getLeaveRequests()` → each `LeaveRequest` → `getEmpRecord()` → the very large `EmployeeRecords` graph → back to `getLeaveRequests()` → **`CircularReferenceException`** (no `circular_reference_handler` and no `#[Ignore]`/groups are configured anywhere; `config/packages/framework.yaml` contains no `serializer` block).
* `getYearlyEmployeeLeaves()` → initialises the **broken `mappedBy: 'selected_leave_policies'` collection** (§3.4) → mapping failure.

Either path aborts the request. Flagged as *statically determined, not runtime-verified*.

### 5.3 `POST /api/leave-policy/create` → `create()`
**Body keys:** `name`, `year`, `description`, `days`, `calendar_color`, `type`, `gender`, `marital`, `increment_amount`, `years_before_increment`, `department`.

**Step-by-step**
1. Decode body (no null check on `$data` — a malformed body yields `null` and every subsequent access warns).
2. `setName($data['name'] ?? "")`, `setYear($data['year'] ?? "")`, `setDescription($data['description'] ?? null)`, `setDays($data['days'] ?? 0)` — these four are tolerant.
3. `setCalendarColor($data['calendar_color'])`, `setGender($data['gender'])`, `setMarital($data['marital'])`, `setIncrementAmount($data['increment_amount'])`, `setYearsBeforeIncrement($data['years_before_increment'])` — **no `??` default; all five are effectively required**, and omitting any produces `null` → **TypeError → 500** (the setters are typed `string`/`int`).
4. `setCarriedOver(false)` — **hardcoded**; the client cannot set `is_carried_over` at creation even though `update()` allows it.
5. Department resolution:
   ```php
   if (isset($data['department'])) {
       if ($data['department'] == 0) { $leavePolicy->setDepartment(null); }  // 0 === "all departments"
       else { setDepartment(find($data['department'])); }
   }
   ```
   **Magic value `0` = all departments.** Note `== 0` is loose, so the strings `"0"`, `""` and `"abc"` all match in PHP 8 semantics for `"abc" == 0`… (PHP 8 changed this: `"abc" == 0` is now `false`, `"" == 0` is `true`). An unknown department id silently yields `null` (= all departments) instead of an error.
6. `validate()` (always empty, see note above), `persist()`, `flush()`.

**Response `201`:** `{"message":"Leave Policy creation successfull"}` *(sic — typo, and the created id is not returned)*.
**Statuses:** `201`, `400` (unreachable in practice).

**Missing validation:** no uniqueness on `(name, year)`; no check that `year` is a valid year; no check that `days >= 0`; no enum for `gender`/`marital`; no colour-format check.

### 5.4 `PUT /api/leave-policy/update/{id}` → `update()`
**Path param:** `{id}`. **Body keys:** same as create **plus** `is_carried_over` (here it *is* honoured).
**Logic:** `find($id)` → `404 {"message":"Leave Policy not found"}`; else assign **all** fields with **no `??` defaults except `description` and `type`** → any omitted key is a TypeError/500. Department is resolved with `find()` **without** the `== 0` "all departments" special case that `create()` has → **inconsistent semantics between create and update** (sending `0` here yields `find(0)` = `null`, which coincidentally still means "all", but by accident).
**Response:** **`201 Created`** `{"message":"Leave Policy update successfull"}` — wrong status code for an update, and the same typo.
**Critical behaviour:** editing `days` **does not propagate** to existing `SelectedEmployeeLeaves.no_of_days` rows (§3.2). Balances already granted keep the old entitlement forever; only future `PUT /api/employee-leaves/update` calls pick up the new number.

### 5.5 `PUT /api/leave-policy/update-list` → `updateList()` **(BROKEN — 500 on every call)**
```php
#[Route('/update-list', methods: ['PUT'])]
public function updateList(Request $request, LeavePolicyRepository $repository, int $id): JsonResponse
```
The path has **no `{id}` placeholder**, but the action requires a scalar `int $id`. Symfony's `ArgumentResolver` cannot resolve it and throws
`RuntimeException: Controller "App\Controller\LeavePolicyController::updateList()" requires the "$id" argument that could not be resolved` → **HTTP 500 unconditionally**.

The body is otherwise identical to `update()`, and the method contains an unused local `$year = $data['year'];`. Despite the plural name it updates **one** record. Dead endpoint; presumably an abandoned bulk-update attempt.

### 5.6 `DELETE /api/leave-policy/delete/{id}` → `delete()`
**Logic:** `find($id)` → `404 {"message":"Leave Policy not found"}`; else `remove()` + `flush()`.
**Response:** `204 No Content` with body `{"message":"Leave Policy deleted successfully"}` — **the body is discarded**, since a 204 response must not carry one.

**Defects**
* **Hard delete with no dependency check.** `leave_request.leave_policies_id` is `NOT NULL` and `selected_employee_leaves.leave_policy_id` references the same row. Deleting a policy that is in use raises a **`ForeignKeyConstraintViolationException` → uncaught 500**, not a friendly 409.
* There is **no `archived` flag on `LeavePolicy`** (unlike `HolidayConfig`/`YearlyHoliday`), so soft-delete is not even possible. Retiring a leave type is impossible without breaking history.
* No authorization.

---

## 6. Controller: `EmployeeLeavesController`

**Class-level:** `#[Route('/api/employee-leaves')]`, no name prefix.
Constructor injects `EntityManagerInterface`, `UserPasswordHasherInterface` (unused), `JWTTokenManagerInterface` (unused), `AuditLog` (unused), `UserAccessValidation` (**unused**), `LeaveRequestRepository` (**unused**).

### Route inventory
| # | HTTP | Full path | Route name | Method | `methods:` restriction |
|---|---|---|---|---|---|
| 1 | **ANY** | `/api/employee-leaves/list` | `app_employee_leaves` | `view_employee_leaves_list()` | **none — all verbs accepted** |
| 2 | **ANY** | `/api/employee-leaves/find/{id}` | `find_employee_leaves` | `view_employee_leaves()` | **none** |
| 3 | **ANY** | `/api/employee-leaves/create` | `app_create_employee_leaves` | `create_employee_leaves()` | **none** |
| 4 | PUT | `/api/employee-leaves/update` | `app_update_employee_leaves` | `update_employee_leaves()` | `['PUT']` |

Routes 1–3 omit `methods:`, so GET/POST/PUT/DELETE/PATCH/HEAD all reach them. In particular **`create` is reachable by GET** (it then fails on the empty body with `400 Invalid JSON data`), and the read endpoints accept POST.

### 6.1 `GET /api/employee-leaves/list` — `app_employee_leaves` → `view_employee_leaves_list()`
**Params:** none.

**Step-by-step**
1. `EmployeeRecords::findAll()` — **every employee, active or not**.
2. **`$selectedYear = "2024";` — HARDCODED YEAR** (line 44). There is no request parameter for the year.
3. For each employee: `YearlyEmployeeLeave::findOneBy(['emp_record' => $employee->getId(), 'year' => $selectedYear])`.
4. If found: `SelectedEmployeeLeaves::findBy(['employee_leave' => $employeeLeaveList->getId()])` and project each row.
5. Append an employee entry.

**Response `200`:**
```jsonc
{
  "message": "Success",
  "emp_with_leave_list": [{
    "emp_id": 42,
    "year": "2024",
    "emp_fullname": "Cruz, Juan Cruz",       // last name twice again
    "employee_leaves": [{
      "emp_leave_id": 11, "year": "2024",
      "selected_leave_id": 7,
      "leave_policy_id": 3, "leave_policy_name": "Vacation Leave",
      "no_of_days": 15, "used_days": 3,
      "carried_over_days": 0, "carry_over_policy": 0, "status": 0
    }]
  }]
}
```

**Defects**
* **Hardcoded `"2024"`** — as of any later year this endpoint returns empty `employee_leaves` for everyone. This is the module's most visible hardcoded value.
* **Severe N+1:** 1 query for employees + 2 queries per employee (`YearlyEmployeeLeave`, `SelectedEmployeeLeaves`) + 1 lazy load per balance row for `LeavePolicy`. For 500 employees with 5 leave types that is ≈ **3,500 queries per request**.
* **`$data` is never initialised** (`$data[] = [...]` at line 67 without a preceding `$data = []`). With zero employees the loop never runs and `return $this->json([... 'emp_with_leave_list' => $data])` references an **undefined variable** → PHP 8 warning and `null` in the payload. (`view_employee_leaves()` at line 86 *does* initialise it — inconsistent.)
* `$leaveItem->getLeavePolicy()->getId()` dereferenced with no null guard on a nullable FK → 500 on orphan rows.
* No pagination, no filtering, no authorization — full company leave-balance dump to any authenticated user.

### 6.2 `GET /api/employee-leaves/find/{id}` — `find_employee_leaves` → `view_employee_leaves()`
**Path param:** `{id}` = **employee record id**.

**Step-by-step**
1. `EmployeeRecords::findOneBy(['id' => $id])` — **no null check**; an unknown id makes `$employee->getId()` a call on null → **500** (never 404).
2. `$selectedYear = "2024";` — hardcoded again (line 85).
3. **The year-filtered lookup is commented out** (line 89) and replaced by
   `YearlyEmployeeLeave::findOneBy(['emp_record' => $employee->getId()])` (line 90) — **no year filter at all**. With multiple yearly rows, Doctrine returns an arbitrary one (effectively the lowest id / insertion order).
4. Project its `SelectedEmployeeLeaves` exactly as §6.1.

**Response `200`:** same envelope as §6.1 but `emp_with_leave_list` is a **single object, not an array** — an inconsistent contract between the two read endpoints.

**Key inconsistency:** the payload advertises `"year": "2024"` (the hardcoded constant) at the top level while `employee_leaves[].year` shows the **actual** year of whichever `YearlyEmployeeLeave` was picked. These two can disagree, and the top-level value is simply wrong.

### 6.3 `POST /api/employee-leaves/create` — `app_create_employee_leaves` → `create_employee_leaves()`
**Body keys:** `emp_id`, `year`, `selected_leaves` — here an **array of objects**: `{no_of_days, used_days, carried_over_days, carry_over_policy, status, leave_policy_id}`.

**Step-by-step**
1. Decode; falsy → `400 {"message":"Invalid JSON data"}`.
2. `EmployeeRecords::find($data['emp_id'])`; missing → `400 {"message":"Employee Record is missing."}`.
3. **Duplicate check (BROKEN):**
   ```php
   findOneBy(['year' => $data['year'], 'year' => $emp_record->getId()])
   ```
   The array literal has a **duplicate `'year'` key**, so PHP keeps only the last one and the criteria collapse to `['year' => <employee id>]`. It therefore searches for a `YearlyEmployeeLeave` whose **`year` column equals the employee id** — comparing a year to a primary key. It essentially never matches (and false-positives when an employee id happens to equal a stored year, e.g. employee id `2024`). `emp_record` is **not part of the criteria at all**. → `400 {"message":"Employee Leave is existing."}` is virtually unreachable, so **duplicate `(employee, year)` envelopes are freely created**.
4. `new YearlyEmployeeLeave()` with `emp_record` and `year`.
5. For each `selected_leaves` item: create `SelectedEmployeeLeaves` with `no_of_days ?? 0.0`, `used_days ?? 0.0`, `carried_over_days ?? 0.0`, `carry_over_policy ?? 0`, `status ?? 0`, optional `leave_policy_id` → `find(LeavePolicy)`, then `setEmployeeLeave($new_emp_leave)` and `persist()`.
6. `persist($new_emp_leave)` + single `flush()`.

**Response:** **`200 OK`** `{"message":"Success"}` — not 201, and the new ids are not returned.
**Statuses:** `200`, `400` (×2).

**Defects**
* The duplicate-key bug above (**hardcoded-style logic error**, `EmployeeLeavesController.php:137`).
* **The client dictates `no_of_days` and even `used_days` directly** — entitlements are not validated against `LeavePolicy.days`, and a balance can be created pre-consumed or with `used_days` exceeding `no_of_days`.
* `leave_policy_id` is optional → a balance row with `leave_policy = null`, which later crashes every listing endpoint (§4.1, §6.1).
* No duplicate check on *(employee_leave, leave_policy)* → the same leave type can be added twice to one envelope, and `LeaveRequestController::create`'s `findOneBy` would then silently pick one.
* No `methods:` restriction; no authorization; no audit; no transaction (though the single flush is atomic in practice).
* `$data['year']` is not validated.

### 6.4 `PUT /api/employee-leaves/update` — `app_update_employee_leaves` → `update_employee_leaves()`
**Body keys:** `emp_id`, `year`, `selected_leaves` — here a **flat array of LeavePolicy ids** (e.g. `[3, 5, 8]`), a **different shape from `create`'s array of objects** for the same key name.

**Step-by-step**
1. Decode; falsy → `400 {"message":"Invalid JSON data"}`.
2. `EmployeeRecords::find($data['emp_id'])`; missing → `400 {"message":"Employee Record is missing."}`.
3. `YearlyEmployeeLeave::findOneBy(['year' => $data['year'], 'emp_record' => $emp_record->getId()])` — **this one is correct** (contrast §6.3). If absent, create and `persist()` a new envelope; otherwise reuse it. So this endpoint is an **upsert** and is the practical way to provision leave.
4. For each `$leave_policy_id`:
   1. `SelectedEmployeeLeaves::findOneBy(['employee_leave' => $emp_leave, 'leave_policy' => $leave_policy_id])`.
   2. **If it already exists → `continue`** (never updated).
   3. `LeavePolicy::find($leave_policy_id)`.
   4. Create the balance row with **`no_of_days = $selected_policy->getDays() ?? 0`** — *this is the one and only place the policy entitlement is transferred to an employee* — and the fixed defaults **`used_days = 0`, `carried_over_days = 0`, `carry_over_policy = 0`, `status = 0`**.
   5. `persist()`.
5. Single `flush()`.

**Response `200`:** `{"message":"Success"}`.

**Defects**
* **Additive only.** Removing an id from `selected_leaves` does **not** delete the balance row — leave types can never be revoked through this API.
* **`continue` means entitlements never refresh.** If `LeavePolicy.days` changes from 15 to 20, existing employees stay at 15 forever (§5.4).
* **No null check on `LeavePolicy::find()`** — an unknown id yields `null` → `$selected_policy->getDays()` → **500**, *after* other rows in the loop were already persisted (they are then discarded because the flush never runs — so partial-input requests fail wholesale, which is at least safe).
* `?? 0` on `getDays()` is dead code — `days` is a non-nullable float column.
* **Carry-over is never computed here** even though this is the natural place to roll the previous year forward (§3.3).
* Newly-created `YearlyEmployeeLeave` is persisted before the loop but there is **no unique constraint** to prevent a concurrent duplicate.
* No authorization, no audit, no transaction.

---

## 7. Controller: `SelectedEmployeeLeavesController`

**Class-level:** `#[Route('/api/selected-employee-leaves', name: 'selected_employee_leaves_')]` → names are the prefix + method name.
Constructor injects `EntityManagerInterface $em`, `SelectedEmployeeLeavesRepository $repository`.

This is a **raw CRUD surface directly over the balance ledger** — the most security-sensitive table in the module — with no guard rails at all.

### Route inventory
| # | HTTP | Full path | Route name | Method |
|---|---|---|---|---|
| 1 | POST | `/api/selected-employee-leaves/create` | `selected_employee_leaves_create` | `create()` |
| 2 | GET | `/api/selected-employee-leaves/list` | `selected_employee_leaves_list` | `list()` |
| 3 | GET | `/api/selected-employee-leaves/find/{id}` | `selected_employee_leaves_read` | `read()` |
| 4 | PUT | `/api/selected-employee-leaves/update/{id}` | `selected_employee_leaves_update` | `update()` |
| 5 | DELETE | `/api/selected-employee-leaves/delete/{id}` | `selected_employee_leaves_delete` | `delete()` |

### 7.1 `POST /api/selected-employee-leaves/create` → `create()`
**Body keys:** `no_of_days`, `used_days`, `carried_over_days`, `carry_over_policy`, `status`, `leave_policy_id`, `employee_leave_id`.

**Logic:** decode (falsy → `400 {"error":"Invalid JSON data"}`); set the five scalars with `?? null`; if `leave_policy_id` is set resolve `LeavePolicy` via `$this->repository->getEntityManager()->find(...)`; likewise `employee_leave_id` → `YearlyEmployeeLeave`; `validate()` (no constraints exist → always passes); `persist()` + `flush()`.

**Response `201`:** `{"id": 7}`.

**Defects**
* **`?? null` against non-nullable typed setters.** `setNoOfDays(float $x)` etc. receive `null` when the key is absent → **TypeError → 500**. The `?? null` gives a false impression of optionality; all five scalars are mandatory.
* Both FKs are optional → **orphan balance rows** with `leave_policy = null` and/or `employee_leave = null` are creatable, and those rows subsequently crash §4.1, §4.2, §4.3, §6.1 and §6.2 on their unguarded `getLeavePolicy()->getName()` calls.
* No uniqueness check on *(employee_leave, leave_policy)*.
* `used_days` is client-supplied and unbounded (may exceed `no_of_days`, may be negative).
* Bypasses `LeavePolicy.days` entirely — entitlements need not match any policy.
* Uses `$this->repository->getEntityManager()` for two lookups while `$this->em` is already injected — inconsistent, and `getEntityManager()` is deprecated-ish surface on the repository.

### 7.2 `GET /api/selected-employee-leaves/list` → `list()`
**Params:** none.
**Logic:** `findAll()` then `$serializer->serialize($leaves, 'json')` returned with `JsonResponse(..., 200, [], true)` (raw-JSON flag).
**Likely 500 — `CircularReferenceException`.** `SelectedEmployeeLeaves` → `leaveRequests` → each `LeaveRequest` → `getSelectedLeave()` → back to the same `SelectedEmployeeLeaves`. With no serialization groups, no `#[Ignore]`, no `max_depth` and no `circular_reference_handler` (nothing configured in `config/packages/framework.yaml`), the default `circular_reference_limit = 1` trips. The graph also drags in `getEmployeeLeave()` → `getEmpRecord()` → the entire `EmployeeRecords` aggregate.
* Even if it serialises, it is an **unpaginated, unfiltered dump of every leave balance in the company**.

### 7.3 `GET /api/selected-employee-leaves/find/{id}` → `read()`
**Path param:** `{id}`.
**Logic:** `find($id)`; missing → `404 {"error":"SelectedEmployeeLeave not found"}`; else serialise the entity as in §7.2 (**same circular-reference exposure**).

### 7.4 `PUT /api/selected-employee-leaves/update/{id}` → `update()`
**Body keys:** `no_of_days`, `used_days`, `carried_over_days`, `carry_over_policy`, `status` — all optional (`?? <current value>`, which is the correct pattern here).
**Logic:** `find($id)` → `404 {"message":"SelectedEmployeeLeave not found"}`; falsy body → `400 {"message":"Invalid JSON data"}`; assign; `validate()`; `flush()`.
**Response `200`:** `{"id": 7}`.

**This is the single most dangerous endpoint in the module.** Any authenticated user — including a rank-and-file employee — can `PUT` their own balance row and set `no_of_days` to `999` or reset `used_days` to `0`, then have leave approved against the fabricated pool. There is **no role check, no ownership check, no audit log, and no history table**. It is also the *only* way carry-over days can ever be entered (§3.3), which is presumably why it exists.
* `leave_policy` and `employee_leave` **cannot** be changed here (no handling), so a mis-linked row must be deleted and recreated.

### 7.5 `DELETE /api/selected-employee-leaves/delete/{id}` → `delete()`
**Logic:** `find($id)` → `404` with body `{"message": ""}` (**empty message string** — a UI showing `message` renders a blank error); else `remove()` + `flush()`.
**Response:** `204 No Content` (body `null`).
**Defects:** hard delete; **no check for dependent `LeaveRequest` rows**. `leave_request.selected_leave_id` is a *nullable* FK without a cascade rule, so MySQL raises a **FK constraint violation → uncaught 500** when requests reference it. Deleting a balance row also silently destroys the consumption history it represents.

---

## 8. Controller: `HolidayConfigController`

**No class-level `#[Route]`** → absolute paths. Note the **inconsistent prefixes**: four routes use `/api/holiday/config/...` while one uses `/api/holiday-config/...`.
Constructor injects `EntityManagerInterface`, `HolidayConfigRepository`.

### Route inventory
| # | HTTP | Full path | Route name | Method |
|---|---|---|---|---|
| 1 | GET | `/api/holiday/config/list` | `app_holiday_config_list` | `list()` |
| 2 | POST | `/api/holiday/config/create` | `app_holiday_config_create` | `create()` — **misnamed: creates YearlyHolidays** |
| 3 | POST | `/api/holiday-config/create-holidays` | `create_multiple_holidays` | `createYearlyHolidays()` — **misnamed: creates ONE HolidayConfig** |
| 4 | GET | `/api/holiday/config/find/{id}` | `app_holiday_config_show` | `show()` |
| 5 | PUT | `/api/holiday/config/update/{id}` | `app_holiday_config_update` | `update()` |
| 6 | DELETE | `/api/holiday/config/delete/{id}` | `app_holiday_config_delete` | `delete()` |

> **Routes 2 and 3 have swapped responsibilities.** `create` (route 2) does *not* create a holiday config — it bulk-generates `YearlyHoliday` rows. `createYearlyHolidays` (route 3) does *not* create yearly holidays — it creates a single `HolidayConfig` template. This naming inversion is a live trap for any integrator.

### 8.1 `GET /api/holiday/config/list` → `list()`
**Params:** none.
**Logic:** `HolidayConfigRepository::findNotArchived()` — the repository's only custom method:
```php
$this->createQueryBuilder('h')
    ->andWhere('h.archived IS NULL OR h.archived = false')
    ->orderBy('h.id', 'ASC')
```
**Response `200`:**
```jsonc
[{"id":1,"name":"New Year's Day","date":"2025-01-01",
  "multiplier_regular":2.0,"multiplier_overtime":2.6}]
```
`date` format `Y-m-d`. The `archived` flag is not exposed. There is **no `type` / `classification` field** — see §10.2.

### 8.2 `POST /api/holiday/config/create` → `create()`  *(bulk-generates YearlyHoliday)*
**Body key:** `year` (only).

**Step-by-step**
1. Decode; falsy → `400 {"message":"Invalid JSON data"}`.
2. `$year = $data['year'];` then `if (!$year)` → `400 {"message":"Year is missing."}` (direct access warns if absent).
3. `HolidayConfig::findAll()` — **includes archived configs** (does not use `findNotArchived()`), so soft-deleted holidays are resurrected into every new year.
4. For each config: `YearlyHoliday::findOneBy(['holiday_config' => $holiday->getId(), 'year' => $year])`; if found → `continue` (idempotent); else create a `YearlyHoliday` with:
   * `holiday_config` = the config,
   * **`date` = `$holiday->getDate()` — the template's date VERBATIM, with its ORIGINAL year**,
   * `year` = the requested `$year`,
   * `archived` left **`null`**.
5. `flush()`.

**Response `201`:** `{"status":"Yearly Holiday created!"}`

**Critical date bug (off-by-year).** The template date is copied **without rebasing the year**. Generating 2026 holidays from configs authored with `2025-01-01` produces rows where `year = "2026"` but `date = 2025-01-01`. `YearlyHolidayController::create()` (§9.1) does this **correctly** by rebuilding the date from `$year . '-' . $originalDate->format('m-d')`. **The two bulk-generators disagree**, and which one the UI calls determines whether the dataset is usable. Any future "is this date a holiday?" lookup keyed on `date` would silently miss every row created through this endpoint.

**Other defects:** N+1 (`findAll()` + one `findOneBy` per config); no `year` format validation; no transaction; no authorization; the endpoint's name and URL imply single-config creation.

### 8.3 `POST /api/holiday-config/create-holidays` → `createYearlyHolidays()`  *(creates ONE HolidayConfig)*
**Body keys:** `name`, `date`, `multiplier_regular`, `multiplier_overtime`.
**Logic:** `new HolidayConfig()`; `setName($data['name'])`; `setDate(new \DateTime($data['date']))`; `setMultiplierRegular(...)`; `setMultiplierOvertime(...)`; `persist()` + `flush()`.
**Response `201`:** `{"status":"Holiday config created!"}` (no id returned).

**Defects**
* No `json_decode` null check and **no key existence checks** — every field is mandatory; a missing key gives `null` → TypeError → 500. A missing `date` gives `new \DateTime(null)` = **now**, silently creating a holiday on today's date.
* `new \DateTime($data['date'])` throws an **uncaught `\Exception` → 500** on an unparseable string, rather than a 400.
* `archived` is left `null` (acceptable — `findNotArchived()` treats `NULL` as active).
* No duplicate check on `(name, date)`; no multiplier range validation (negative or zero multipliers accepted).
* **No holiday-type field is settable** because none exists (§10.2).
* No authorization.

### 8.4 `GET /api/holiday/config/find/{id}` → `show()`
**Logic:** `find($id)` → `404 {"status":"Holiday config not found!"}`; else a manual projection identical in shape to §8.1's elements.
**Defect:** uses `find()`, not `findNotArchived()`, so **archived configs are still readable** — inconsistent with `list()`. Note the error key here is `status`, whereas the leave controllers use `message`.

### 8.5 `PUT /api/holiday/config/update/{id}` → `update()`
**Body keys:** `name`, `date`, `multiplier_regular`, `multiplier_overtime` (all mandatory in practice — no `??` defaults).
**Logic:** `find($id)` → `404 {"status":"Holiday config not found!"}`; assign all four; `flush()`.
**Response `200`:** `{"status":"Holiday config updated!"}`

**Defects:** editing the template `date` **does not propagate** to already-generated `YearlyHoliday` rows, and §9.4 shows the yearly date cannot be edited either — so a corrected holiday date can never be fixed for an existing year without direct DB access. No null checks; no validation; archived configs are editable; no authorization.

### 8.6 `DELETE /api/holiday/config/delete/{id}` → `delete()`
**Logic:** `find($id)` → `404 {"status":"Holiday config not found!"}`; else **`setArchived(true)`**, `persist()`, `flush()`.
**Response `200`:** `{"status":"Holiday config deleted!"}` — a **soft delete** despite the message.
**Defect:** the dependent `YearlyHoliday` rows are **not archived**, so `GET /api/yearly-holiday/list` keeps returning instances of a "deleted" holiday, and §8.2's `findAll()` will regenerate it for future years. Archiving is not cascaded and not reversible through the API (**no un-archive endpoint exists for either entity**).

---

## 9. Controller: `YearlyHolidayController`

**Class-level:** `#[Route('/api/yearly-holiday', name: 'yearly_holiday_')]`.
Constructor injects `EntityManagerInterface $em`, `YearlyHolidayRepository $repository`.

### Route inventory
| # | HTTP | Full path | Route name | Method |
|---|---|---|---|---|
| 1 | POST | `/api/yearly-holiday/create-list` | `yearly_holiday_create` | `create()` |
| 2 | GET | `/api/yearly-holiday/list` | `yearly_holiday_list` | `list()` |
| 3 | GET | `/api/yearly-holiday/find/{id}` | `yearly_holiday_read` | `read()` |
| 4 | PUT | `/api/yearly-holiday/update/{id}` | `yearly_holiday_update` | `update()` |
| 5 | DELETE | `/api/yearly-holiday/delete/{id}` | `yearly_holiday_delete` | `delete()` |

### 9.1 `POST /api/yearly-holiday/create-list` → `create()`
**Body key:** `year` (only).

**Step-by-step**
1. `$year = $data['year'] ?? null;` → empty → `404 {"message":"Year not found."}` (**404 for a validation failure**; should be 400).
2. `HolidayConfig::findAll()` — again **includes archived** configs.
3. For each config:
   1. `$validator->validate($holiday_item)` — `HolidayConfig` has **no constraints**, so this always passes; on failure it would return `400` with `(string) $errors` (a human-readable dump, not JSON).
   2. `$originalDate = $holiday_item->getDate();` if it is a `\DateTimeInterface`:
      * **`$adjustedDate = \DateTime::createFromFormat('Y-m-d', $year . '-' . $originalDate->format('m-d'));`** — rebases the month/day onto the requested year (**this is the correct behaviour that §8.2 lacks**).
      * `new YearlyHoliday()` with `holiday_config`, `date = $adjustedDate`, `year = $year`, `archived` left `null`; `persist()`.
4. `flush()`.

**Response `201`:** `{"message":"Creation successful"}`
**Statuses:** `201`, `404`, `400` (unreachable).

**Date-handling defects**
* **`createFromFormat` without a leading `!`** does not reset the time fields, so the object carries the **current time-of-day**. Harmless in practice because the column is `DATE`, but it makes the in-memory object misleading.
* **Feb 29 overflow:** a config dated `02-29` rebased onto a non-leap year produces `"2026-02-29"`, which `createFromFormat` **silently rolls over to 2026-03-01** instead of failing. No leap-year guard.
* **No `year` format validation.** `"25"` yields `"25-01-01"`, parsed as **year 25 AD**. A non-numeric year makes `createFromFormat` return `false` → `setDate(false)` against `?\DateTimeInterface` → **TypeError → 500**.
* **No duplicate check** — unlike §8.2, this endpoint has **no `findOneBy` guard**. Calling it twice for the same year **duplicates every holiday**, and there is no unique constraint on `(holiday_config, year)`. Running both generators for the same year produces two divergent row sets (one with correct dates, one with §8.2's wrong-year dates).
* No transaction; no authorization.

### 9.2 `GET /api/yearly-holiday/list` → `list()`
**Params:** none — **no `year` filter**, so the client receives every year ever generated and must filter locally.
**Logic:** `YearlyHolidayRepository::findNotArchived()` (`y.archived IS NULL OR y.archived = false`, `ORDER BY y.id ASC`) + manual projection.
**Response `200`:**
```jsonc
[{
  "id": 10,
  "holiday_config_id": 1,
  "holiday_name": "New Year's Day",
  "holiday_multiplier_regular": 2.0,
  "holiday_multiplier_ot": 2.6,
  "date": "2026-01-01",     // nullable → null via `?->format('Y-m-d')`
  "year": "2026"
}]
```
**Defects:** `getHolidayConfig()` is dereferenced unguarded (safe here — the FK is `nullable: false`); **archived `HolidayConfig` rows still surface** through their non-archived yearly instances (§8.6); N+1 lazy load of `HolidayConfig` per row.

### 9.3 `GET /api/yearly-holiday/find/{id}` → `read()`
**Logic:** `find($id)` → `404 {"error":"Holiday not found"}`; else `$serializer->serialize($holiday, 'json')`.
**Defect:** the serialised shape is **completely different** from `list()`'s projection, and it traverses `holiday_config` → `yearlyHolidays` → back to the holiday → **`CircularReferenceException` risk** (same root cause as §7.2). Also uses the error key `error` while its sibling controllers use `message`/`status`.

### 9.4 `PUT /api/yearly-holiday/update/{id}` → `update()`
**Body key:** `holiday_config_id` — **and nothing else is honoured.**
**Step-by-step:** `find($id)` → `404 {"error":"Holiday not found"}`; `$holidayId = $data['holiday_config_id'] ?? null`; empty → `400 {"error":"Holiday ID not found"}`; `HolidayConfig::find($holidayId)` → missing → `404 {"error":"Holiday Config not found"}`; `setHolidayConfig(...)`; `validate()`; `flush()`.
**Response `200`:** `{"message":"Yearly holiday updated"}`

**Major functional gap:** the method **never updates `date` or `year`**. Any `date`/`year` supplied in the body is **silently ignored**. Consequently **a yearly holiday's date can never be corrected through the API** — which breaks the primary real-world use case for a per-year holiday table: *movable* Philippine holidays (Eid'l Fitr, Eid'l Adha, Chinese New Year, Holy Week, and the "nearest Monday" holiday-economics proclamations) change date every year. The only workaround is delete + regenerate, and regeneration always rebases to the template's fixed month/day. This effectively reduces `YearlyHoliday` to a fixed-date mirror of `HolidayConfig`.

### 9.5 `DELETE /api/yearly-holiday/delete/{id}` → `delete()`
**Logic:** `find($id)` → `404 {"error":"Yearly Holiday not found"}`; else `setArchived(true)`, `persist()`, `flush()`.
**Response:** `204 No Content` (body `null`). Soft delete; **no un-archive endpoint**.

---

## 10. Holiday Rules — consolidated

### 10.1 `HolidayConfig` vs `YearlyHoliday`
| | `HolidayConfig` | `YearlyHoliday` |
|---|---|---|
| Role | **Template / catalogue** of recurring holidays | **Materialised instance** for one specific year |
| Grain | one row per holiday name | one row per *(holiday, year)* |
| `date` | `DATE`, **non-null** — carries a full year that is meaningless except as a month/day carrier | `DATE`, **nullable** — the actual observed date |
| `year` | *(absent)* | `VARCHAR(255)` |
| Pay multipliers | `multiplier_regular`, `multiplier_overtime` | *(inherited via FK — not duplicated)* |
| Soft delete | `archived` (nullable bool) | `archived` (nullable bool) |
| Generated by | manual (`POST /api/holiday-config/create-holidays`) | bulk from templates — **two competing endpoints**, §8.2 and §9.1 |

The intended flow: define each holiday once as a `HolidayConfig`, then once per year "roll forward" the catalogue into dated `YearlyHoliday` rows that could, in principle, be adjusted for movable feasts. **The adjustment step is not implemented** (§9.4).

### 10.2 Regular vs Special Non-Working — NOT MODELLED
There is **no `type`, `classification`, `category`, `is_regular` or `is_special` column** on either entity, and no enum anywhere. Philippine labour law distinguishes:
* **Regular holidays** — 100% pay if unworked, 200% if worked;
* **Special (non-working) days** — no-work-no-pay, 130% if worked.

The **only** way the system can express this distinction is implicitly, through the numeric `multiplier_regular` / `multiplier_overtime` values an administrator types in (e.g. `2.0`/`2.6` for regular vs `1.3`/`1.69` for special). Nothing validates, groups, labels or reports on those numbers, and **no code reads them**. Reporting "hours worked on special non-working days" is impossible without adding a column.

### 10.3 How does the system decide whether a given date is a holiday?
**It does not.** There is no such function, service, helper, repository method or query anywhere in `src/`. Confirmed by an exhaustive case-insensitive search for `holiday` across `src/` — the only hits outside the two holiday controllers/entities/repositories are:
* `LoginController.php:175,288` — echoing the `holiday_config` RBAC permission array;
* `SubModules.php:108,192,226,462-469` — the RBAC permission property;
* `SuperAdminController.php:348,404` — seeding that permission;
* `PayrollGenerationController.php:1136` — `$data['sal_adj_4hrs_more_weekend_holiday']`, a **manually entered salary-adjustment amount** on `SalaryAdjustment`, unrelated to the holiday tables.

`YearlyHolidayRepository` and `HolidayConfigRepository` expose only `findNotArchived()` — **there is no `findByDate()`, no `isHoliday()`, no date-range query**. The `date` column is never queried.

### 10.4 Effect on DTR and pay — none
* **DTR:** `DTRController`, `DTRReportController`, `CheckEmpDtrController`, `AttendanceController` and `DTRAdjustmentsController` contain zero holiday references. A holiday is an ordinary day; if the employee does not log in, the day is simply absent.
* **Payroll:** `PayrollGenerationController` never loads `HolidayConfig` or `YearlyHoliday`. `multiplier_regular` and `multiplier_overtime` are **write-only data**.
* **Holiday premium pay is therefore NOT implemented.** Any holiday premium must be entered by hand through the `SalaryAdjustment` mechanism (`sal_adj_*` fields), with no link to the holiday calendar and no audit that the amount matches the multiplier.
* **Unworked regular-holiday pay is NOT implemented** either — employees are simply unpaid for the day.

**Conclusion:** the holiday module is a **standalone reference calendar for the UI**. It is fully disconnected from time-keeping and compensation.

---

## 11. Leave ↔ Payroll — consolidated

| Question | Answer |
|---|---|
| Does approval credit pay for paid leave? | **No.** Payroll never reads `LeaveRequest`. |
| Does unpaid leave create a deduction? | **No explicit deduction.** The day simply has no DTR record, so it earns nothing — de-facto no-work-no-pay applied **uniformly to paid and unpaid leave alike**. |
| Is a paid leave day converted to payable hours? | **No.** There is no leave-to-DTR bridge, no synthetic attendance record, no `AttendanceTypes` entry written on approval. |
| Is leave prorated against the payroll period? | **No.** `LeaveRequest.year` is a whole-year string; nothing intersects `date_start`/`date_end` with a payroll cutoff (`date_start`/`date_end` of a payroll run). A leave spanning two cutoffs is not split. |
| Does the payslip show leave? | **No.** `PayslipController` has no leave reference. |
| Are leave balances shown on payroll reports? | **No.** `PayrollReportsController` has no leave reference. |
| Is there a leave-monetisation / conversion-to-cash path? | **No.** Nothing converts unused `no_of_days - used_days` into pay, and there is no year-end encashment routine. |

**Practical consequence:** the leave module is an **HR record-keeping and balance-tracking system only**. The `with pay` intent expressed in `LeavePolicy.type` (if populated at all) has **no financial effect whatsoever**. Payroll correctness for leave days depends entirely on manual salary adjustments.

---

## 12. Validation Matrix

| Rule | Implemented? | Where / why not |
|---|---|---|
| **Overlap detection** (new leave colliding with existing approved leave) | **NO** | `create()` never queries existing `LeaveRequest` rows. Unlimited overlapping requests, all approvable. |
| **Balance sufficiency** | **Partial — at approval only** | `approveLeaveRequest()` line 339-342: `(no_of_days + carried_over_days) - used_days < total_days_requested` → `400 "Not Enough Leaves."`. Never checked at filing; no pending-reservation, so N pending requests can each pass the check individually and collectively overdraw only if approved sequentially (each re-reads the updated `used_days`, so sequential approval is safe — **but concurrent approval races**, since there is no lock, no `SELECT … FOR UPDATE` and no transaction). |
| **Duplicate prevention** (same dates twice) | **NO** | No unique constraint, no query. |
| **Past-date prevention** | **NO** | `date_start` is unconstrained; back-dating is unlimited. |
| **`date_end >= date_start`** | **NO** | `DateInterval::$days` is absolute, so reversed ranges silently produce a positive day count. |
| **Weekend / rest-day exclusion** | **NO** | `$interval->days + 1` counts calendar days. |
| **Holiday exclusion from leave day count** | **NO** | Holiday data exists but is never consulted (§10.3). |
| **Half-day consistency with date range** | **NO** | `is_half_day` forces `0.5` regardless of span. |
| **Max consecutive days / notice period** | **NO** | No such fields or checks. |
| **Gender / marital eligibility** | **NO** | Fields exist on `LeavePolicy`; never compared to `EmployeeRecords.gender` / `.civil_status` (§2.2.4). |
| **Department eligibility** | **NO** | `LeavePolicy.department` never compared to the employee's department. |
| **Tenure gate (`years_before_increment`)** | **NO** | `EmployeeRecords.date_hired` exists but is never used for leave. |
| **Status transition validity** | **NO** | `setStatus($data['status'])` accepts any string; no state machine. |
| **Double-approval guard** | **NO** | The most severe gap — re-approving re-debits (§4.7). |
| **Attachment required for certain types** | **NO** | `document` is a mandatory free string for *all* types; no upload, no MIME/size check. |
| **`YearlyEmployeeLeave` uniqueness per (employee, year)** | **NO** | No DB constraint; §6.3's duplicate-key bug actively defeats the app-level check. |
| **`SelectedEmployeeLeaves` uniqueness per (envelope, policy)** | **NO** | Checked in §6.4 only; bypassed by §6.3 and §7.1. |
| **Entity-level assertions** | **NO** | Not one `#[Assert\*]` constraint exists on any of the six entities, so every `$validator->validate()` call is a no-op. |
| **Year format** | **NO** | `year` is `VARCHAR(255)` everywhere; `"2O25"` is storable. |

### 12.1 Date formats used
| Context | Format |
|---|---|
| `LeaveRequest` request-body input | anything `\DateTime::__construct()` parses (unvalidated; a bad string throws an uncaught exception → 500) |
| `LeaveRequest` JSON output | `'Y-m-d H:i:s'` |
| `HolidayConfig` / `YearlyHoliday` JSON output | `'Y-m-d'` |
| `YearlyHoliday` generation | `\DateTime::createFromFormat('Y-m-d', $year.'-'.$original->format('m-d'))` |
| `year` fields (all entities) | **`VARCHAR(255)` strings**, compared with loose Doctrine criteria |

### 12.2 Date-loop / off-by-one summary
* `LeaveRequestController::create()` line 179 — **`$interval->days + 1`**. Correct for an inclusive range; **over-counts** because weekends and holidays are never excluded; **short-circuited to `0.5`** whenever `is_half_day` is truthy, ignoring the range entirely.
* Midnight normalisation (`setTime(0,0,0)`, lines 170-171) is applied to the **counting** objects but **not** to the **persisted** objects (lines 186-187 re-parse the raw strings) — so stored timestamps may carry a time component that the day count ignored.
* `HolidayConfigController::create()` line 65 — **year is never rebased** (`setDate($holiday->getDate())`), producing `YearlyHoliday` rows whose `date` year contradicts their `year` column. **This is the clearest off-by-one(-year) bug in the module.**
* `YearlyHolidayController::create()` line 52 — correct rebasing, but no `!` prefix (residual time-of-day) and **Feb 29 rolls over to Mar 1** on non-leap years.

---

## 13. Known Hacks & Weak Spots (register)

### 13.1 Raw SQL
**None.** Every query in the six controllers goes through Doctrine's `find` / `findBy` / `findOneBy` / `findAll`. The only DQL is the two `findNotArchived()` query builders. There is **no `createNativeQuery`, no `getConnection()->executeQuery`, no string-concatenated SQL** in the leave/holiday module — so **no SQL-injection surface here**. (This is the module's one genuine strength.)

### 13.2 Loop queries (N+1)
| Location | Pattern | Cost |
|---|---|---|
| `EmployeeLeavesController::view_employee_leaves_list` | `findAll()` employees, then 2 queries per employee + lazy `LeavePolicy` per balance row | ≈ **3,500 queries** at 500 employees × 5 types |
| `LeaveRequestController::list` / `approvedList` / `findEmployeeLeave` | lazy `EmployeeRecords`, `SelectedEmployeeLeaves`, `LeavePolicy`, `updated_by` per row | 3–4 extra queries per request row |
| `HolidayConfigController::create` | `findAll()` configs + one `findOneBy` per config | N+1 |
| `YearlyHolidayController::create` | `findAll()` configs, one INSERT per config | N inserts, single flush |
| `YearlyHolidayController::list` | lazy `HolidayConfig` per row | N+1 |
| `EmployeeLeavesController::update_employee_leaves` | one `findOneBy` + one `find` per policy id | 2N |
| `NotificationService` (via approval) | one INSERT per Active employee in dept `HRS` | N inserts inside the approval path |

No `JOIN FETCH`, no `setFetchMode`, no pagination anywhere in the module.

### 13.3 Hardcoded values / dates / IDs
| Value | Location | Impact |
|---|---|---|
| **`$selectedYear = "2024"`** | `EmployeeLeavesController.php:44` (`/list`) and `:85` (`/find/{id}`) | The leave-balance listing is frozen to 2024 and returns empty results for any later year. **Highest-visibility hardcode in the module.** |
| **`'HRS'`** department code | `LeaveRequestController.php:347` | Approval notification target. If the code is renamed or missing → `getDivision()` on `null` → **500 during approval**. |
| **`"DEP_ONLY"`** notification type | `LeaveRequestController.php:348` | Fans out to the entire HRS department. |
| **`setCarriedOver(false)`** | `LeavePolicyController.php:93` | Client cannot set the flag at creation. |
| **`0` = "all departments"** magic number | `LeavePolicyController.php:96` | Undocumented sentinel; absent from `update()`. |
| `setStatus(0)` on create | `LeaveRequestController.php:191` | The only place Pending is defined. |
| `"1"` string comparison for Approved | `LeaveRequestController.php:337` | Loose `==`; no constant. |
| `findBy(['status' => 1])` int vs `VARCHAR` | `LeaveRequestController.php:80` | Relies on MySQL type coercion. |
| Fixed defaults `used=0, carried=0, carry_policy=0, status=0` | `EmployeeLeavesController.php:212-215` | Prevents carry-over from ever being provisioned automatically. |
| `"4"` notification type (string, not int) | `NotificationService.php:137` | Type inconsistency with the int types `0/1/2`. |

**Status codes are magic numbers throughout** — there is no `LeaveStatus` enum, no class constants, and `status` is a `VARCHAR` rather than a `smallint`/enum.

### 13.4 Missing authorization (systemic)
**Zero of the 24 routes** performs any authorization beyond the global `IS_AUTHENTICATED_FULLY`:
* no `#[IsGranted]`, no `denyAccessUnlessGranted()`, no Voter, no `getUser()` call anywhere in the six controllers;
* `UserAccessValidation` is injected into two controllers and **never called**, and its `switch` does not even implement the leave/holiday submodules (§1.2);
* **`AuditLog` is injected into two controllers and never called** — no leave action is audit-logged, despite `AuditTrailLog` existing.

Concrete abuses available to any authenticated employee:
1. `PUT /api/selected-employee-leaves/update/{id}` → set own `no_of_days = 999` or `used_days = 0`.
2. `PUT /api/leave/request/approve/{id}` with `{"status":"1","user_id":<anyone>}` → **self-approve**, and forge `updated_by` to another person.
3. `POST /api/leave/request/create` with an arbitrary `emp_record_id` → file leave in a colleague's name.
4. `DELETE /api/leave/request/delete/{id}` → destroy anyone's leave history.
5. `GET /api/leave/request/list` → read every employee's leave reasons (privacy/PII exposure).
6. `DELETE /api/holiday/config/delete/{id}` → archive company holidays.
7. `POST /api/yearly-holiday/create-list` → duplicate the entire holiday calendar (§9.1).

The approver identity is taken from the **request body** (`user_id`), not from the JWT — so even the weak trail that exists is untrustworthy.

### 13.5 Missing transactions
No `beginTransaction()` / `commit()` / `rollback()` and no `EntityManager::wrapInTransaction()` in the entire module. Highest-risk spots:
* **`approveLeaveRequest()`** — mutates `used_days`, mutates `status`, and inserts N notifications; `createNotificationForSpecificUser()` performs its **own `flush()` mid-method**, splitting the operation across separate implicit transactions. A failure after that inner flush leaves notifications sent for an approval that was never persisted, or a debited balance with a stale status.
* **`EmployeeLeavesController::create_employee_leaves` / `update_employee_leaves`** — a null `LeavePolicy` mid-loop throws after earlier `persist()` calls (safe only because the final `flush()` never runs).
* **`HolidayConfigController::create` / `YearlyHolidayController::create`** — bulk generation with a single trailing flush; a mid-loop exception aborts the whole batch (acceptable), but there is no idempotency key.

### 13.6 Concurrency
No optimistic locking (`#[ORM\Version]`) and no pessimistic locks on `SelectedEmployeeLeaves`. Two simultaneous approvals for the same balance row both read the same `used_days` and both write `used_days + their own days` → **lost update, balance overdrawn**. The §12 sufficiency check offers no protection under concurrency.

### 13.7 Broken / dead code inventory
| Item | Location | Nature |
|---|---|---|
| `PUT /api/leave/request/update/{id}` | `LeaveRequestController.php:228` | **Unreachable** — route name `app_leave_request_update` reused at line 326; `RouteCollection::add()` evicts the first. |
| `LeaveRequestController::show()` | line 202 | **Shadowed** — identical path+method to `find_emp_leave_request` (line 109), which registers first and always matches. |
| `LeavePolicyController::updateList()` | line 166 | **500 on every call** — requires `int $id` but `/update-list` has no `{id}` placeholder. |
| `LeavePolicy::$yearlyEmployeeLeaves` M2M | `LeavePolicy.php:64` | `mappedBy: 'selected_leave_policies'` — **the owning field does not exist**; fails on first collection access (§3.4). |
| `LeavePolicy::addYearlyEmployeeLeaf/removeYearlyEmployeeLeaf` | lines 267-284 | Commented out. |
| `LeaveRequestController::approveLeaveRequest` (old version) | lines 252-324 | 76 lines of commented-out code referencing a removed `getLeavePoliciesJson()` API and containing its own bugs (`'emp_record '` with a trailing space; `$dateStart->diff($dateEnd)->days` without `+1`). Evidence of the JSON-column → `SelectedEmployeeLeaves` refactor. |
| Unused injected services | `LeaveRequestController` (`passhasher`, `jwtManager`, `auditlog`, `validateAccess`), `EmployeeLeavesController` (same + `leaveRequestRepository`), `LeavePolicyController` (`serializer`) | Dead dependencies |
| Unused local `$year` | `LeavePolicyController.php:176` | Dead variable |

### 13.8 API-consistency defects
* **Error-key drift:** `message` (leave controllers, `YearlyHolidayController::update`), `status` (`HolidayConfigController`), `error` (`SelectedEmployeeLeavesController`, most of `YearlyHolidayController`). Three conventions across six controllers.
* **Response-shape drift:** bare arrays (`LeaveRequestController`, `LeavePolicyController::index`, `YearlyHolidayController::list`, `HolidayConfigController::list`) vs `{message, emp_with_leave_list}` envelopes (`EmployeeLeavesController`) vs raw serialised entities (`SelectedEmployeeLeavesController`, `LeavePolicyController::show`, `YearlyHolidayController::read`).
* **`emp_with_leave_list`** is an **array** in `/list` but an **object** in `/find/{id}`.
* **`selected_leaves`** is an **array of objects** in `POST /api/employee-leaves/create` but an **array of ints** in `PUT /api/employee-leaves/update`.
* **Wrong status codes:** `201` returned for updates (`LeavePolicyController::update`); `200` returned for creates (`EmployeeLeavesController::create_employee_leaves`); `204` returned **with a JSON body** (`LeavePolicyController::delete`); `404` used for a missing-parameter validation error (`YearlyHolidayController::create`).
* **Created ids not returned** by `POST /api/leave/request/create`, `POST /api/leave-policy/create`, `POST /api/employee-leaves/create`, both holiday creators.
* **Typo** `"creation successfull"` / `"update successfull"` in `LeavePolicyController`.
* **`emp_name` renders the last name twice** in 4 places (`LeaveRequestController.php:55,87,118`; `EmployeeLeavesController.php:70,113`).
* Missing `methods:` on 3 `EmployeeLeavesController` routes → all verbs accepted.

---

## 14. Quick-Reference: all 24 routes

| HTTP | Path | Route name | Controller::method |
|---|---|---|---|
| GET | `/api/leave/request/list` | `app_leave_request_list` | `LeaveRequestController::list` |
| GET | `/api/leave/request/list-approved` | `app_leave_request_list_approved` | `LeaveRequestController::approvedList` |
| GET | `/api/leave/request/find/{id}` | `find_emp_leave_request` | `LeaveRequestController::findEmployeeLeave` |
| POST | `/api/leave/request/create` | `app_leave_request_create` | `LeaveRequestController::create` |
| GET | `/api/leave/request/find/{id}` | `app_leave_request_show` | `LeaveRequestController::show` ⚠ shadowed |
| PUT | `/api/leave/request/update/{id}` | `app_leave_request_update` | `LeaveRequestController::update` ⚠ unreachable |
| PUT | `/api/leave/request/approve/{id}` | `app_leave_request_update` | `LeaveRequestController::approveLeaveRequest` |
| DELETE | `/api/leave/request/delete/{id}` | `app_leave_request_delete` | `LeaveRequestController::delete` |
| GET | `/api/leave-policy/list` | `app_controller_leavepolicycontroller_index` | `LeavePolicyController::index` |
| GET | `/api/leave-policy/find/{id}` | `app_controller_leavepolicycontroller_show` | `LeavePolicyController::show` ⚠ circular-ref |
| POST | `/api/leave-policy/create` | `app_controller_leavepolicycontroller_create` | `LeavePolicyController::create` |
| PUT | `/api/leave-policy/update/{id}` | `app_controller_leavepolicycontroller_update` | `LeavePolicyController::update` |
| PUT | `/api/leave-policy/update-list` | `app_controller_leavepolicycontroller_updatelist` | `LeavePolicyController::updateList` ⚠ always 500 |
| DELETE | `/api/leave-policy/delete/{id}` | `app_controller_leavepolicycontroller_delete` | `LeavePolicyController::delete` |
| ANY | `/api/employee-leaves/list` | `app_employee_leaves` | `EmployeeLeavesController::view_employee_leaves_list` |
| ANY | `/api/employee-leaves/find/{id}` | `find_employee_leaves` | `EmployeeLeavesController::view_employee_leaves` |
| ANY | `/api/employee-leaves/create` | `app_create_employee_leaves` | `EmployeeLeavesController::create_employee_leaves` |
| PUT | `/api/employee-leaves/update` | `app_update_employee_leaves` | `EmployeeLeavesController::update_employee_leaves` |
| POST | `/api/selected-employee-leaves/create` | `selected_employee_leaves_create` | `SelectedEmployeeLeavesController::create` |
| GET | `/api/selected-employee-leaves/list` | `selected_employee_leaves_list` | `SelectedEmployeeLeavesController::list` ⚠ circular-ref |
| GET | `/api/selected-employee-leaves/find/{id}` | `selected_employee_leaves_read` | `SelectedEmployeeLeavesController::read` ⚠ circular-ref |
| PUT | `/api/selected-employee-leaves/update/{id}` | `selected_employee_leaves_update` | `SelectedEmployeeLeavesController::update` ⚠ balance tampering |
| DELETE | `/api/selected-employee-leaves/delete/{id}` | `selected_employee_leaves_delete` | `SelectedEmployeeLeavesController::delete` |
| GET | `/api/holiday/config/list` | `app_holiday_config_list` | `HolidayConfigController::list` |
| POST | `/api/holiday/config/create` | `app_holiday_config_create` | `HolidayConfigController::create` ⚠ makes YearlyHolidays, wrong year |
| POST | `/api/holiday-config/create-holidays` | `create_multiple_holidays` | `HolidayConfigController::createYearlyHolidays` ⚠ makes one HolidayConfig |
| GET | `/api/holiday/config/find/{id}` | `app_holiday_config_show` | `HolidayConfigController::show` |
| PUT | `/api/holiday/config/update/{id}` | `app_holiday_config_update` | `HolidayConfigController::update` |
| DELETE | `/api/holiday/config/delete/{id}` | `app_holiday_config_delete` | `HolidayConfigController::delete` (soft) |
| POST | `/api/yearly-holiday/create-list` | `yearly_holiday_create` | `YearlyHolidayController::create` |
| GET | `/api/yearly-holiday/list` | `yearly_holiday_list` | `YearlyHolidayController::list` |
| GET | `/api/yearly-holiday/find/{id}` | `yearly_holiday_read` | `YearlyHolidayController::read` |
| PUT | `/api/yearly-holiday/update/{id}` | `yearly_holiday_update` | `YearlyHolidayController::update` ⚠ ignores date/year |
| DELETE | `/api/yearly-holiday/delete/{id}` | `yearly_holiday_delete` | `YearlyHolidayController::delete` (soft) |

*(30 registered route declarations; 2 are unreachable and 1 always 500s, leaving 27 functional endpoints. The 8 `LeaveRequestController` declarations collapse to 6 reachable.)*

---

## 15. Priority Remediation Shortlist

| # | Severity | Issue | Fix sketch |
|---|---|---|---|
| 1 | **Critical** | Double-approval re-debits `used_days` (§4.7) | Guard `if ($leaveRequest->getStatus() == 1) return 400;` before the debit |
| 2 | **Critical** | `PUT /selected-employee-leaves/update/{id}` lets anyone rewrite balances (§7.4) | Role gate + audit log + restrict to HR |
| 3 | **Critical** | Self-approval; `updated_by` taken from the request body (§4.7) | Derive the approver from the JWT; add a manager/HR voter; reject self-approval |
| 4 | **Critical** | No authorization on any of the 24 routes (§13.4) | Wire `UserAccessValidation` (adding the missing submodule cases) or add Voters |
| 5 | **High** | Hardcoded `"2024"` (§6.1, §6.2) | Accept a `year` query parameter; default to `date('Y')` |
| 6 | **High** | `HolidayConfigController::create` does not rebase the year (§8.2) | Reuse `YearlyHolidayController::create`'s logic; delete one of the two generators |
| 7 | **High** | No overlap / past-date / duplicate validation on filing (§12) | Add a date-range intersection query against non-rejected requests |
| 8 | **High** | Approval reversal and deletion never refund `used_days` (§3.5) | Credit back on 1 → 0/2 transitions and on delete-of-approved |
| 9 | **High** | Duplicate `'year'` array key defeats the duplicate check (§6.3) | `['year' => $data['year'], 'emp_record' => $emp_record]` + a DB unique index |
| 10 | **Medium** | Route-name collision hides `update()`; path collision hides `show()` (§13.7) | Rename to `app_leave_request_approve`; give `show()` a distinct path |
| 11 | **Medium** | Weekends/holidays counted as leave days (§4.4) | Exclude non-working days using `Shifts` + `YearlyHoliday` |
| 12 | **Medium** | Circular-reference 500s on raw entity serialisation (§5.2, §7.2, §7.3, §9.3) | Replace with explicit projections or add serialization groups |
| 13 | **Medium** | No transactions / no locking around approval (§13.5, §13.6) | `wrapInTransaction()` + pessimistic write lock on the balance row |
| 14 | **Medium** | `YearlyHoliday` date can never be edited (§9.4) | Honour `date` and `year` in the update payload |
| 15 | **Low** | `status` is an unvalidated `VARCHAR` magic number | Introduce a PHP 8.1 backed enum + a smallint column |
| 16 | **Low** | `emp_name` repeats the last name (5 sites) | Fix the concatenation |

---

*End of `04-backend-leave.md`. Scope: LEAVE and HOLIDAY only. Findings are from static analysis of the read-only source tree; items marked "likely 500" were determined statically and not executed.*
