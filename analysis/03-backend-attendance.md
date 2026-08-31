# WCHRIS API — Attendance / DTR / Shifts / Overtime Business-Logic Analysis

> Scope: ATTENDANCE, DTR (daily time record), SHIFTS, OVERTIME, DTR ADJUSTMENTS, and the
> biometric/time-log sync pipeline. Leave and Holiday subsystems are OUT OF SCOPE for this file
> (covered separately). Target dir: `/mnt/f/laragon/www/wchhris-api` (READ-ONLY analysis).
> Stack: Symfony 7.0, Doctrine ORM 3.1, PHP >=8.2 (no `declare(strict_types=1)` anywhere →
> implicit scalar coercion), MySQL backend, JWT auth via Lexik.

---

## 1. SYSTEM CONTEXT & DATA SOURCES

Raw time punches (biometric / device) live in a **SEPARATE external database**, not in the
application DB. The app holds connection credentials for that device DB in the `sync_connection`
table (entity `SyncConnection`: `id`, `username`, `password`, `dbname`, `host`).

Two inbound pipelines populate the app's `worker_logs` table:

1. **Pull sync from the external device DB** — `SyncWorkerController::syncLogs()` (`POST /sync/worker`,
   actually `GET|POST` since no `methods` is set; see §9). It reads `SyncConnection` row `id = 1`,
   opens a raw **PDO** connection (`mysql:host=…;dbname=…;charset=utf8mb4`), and copies rows from the
   device tables `worker` and `worker_logs`.
   - Device table `worker` columns read: `worker_id`, `first_name`, `last_name`, `position`,
     `photo`, `er_name`, `er_contact`, `status`.
   - Device table `worker_logs` columns read: `id`, `user_id`, `login_date`, `logout_date`, `type`.
   - **NOTE:** There is a `App\Service\SyncDatabaseConnection` class (extends Doctrine `Connection`)
     whose constructor re-connects to the `sync_connection` DB, but it is **NOT injected/used** by
     `SyncWorkerController` — the controller builds its own PDO. The service is effectively dead code.

2. **Manual CSV/bulk upload** — `ManpowerController::createWorkerLogs()` (`POST /api/worker_logs/create`).
   Reads a JSON array of punch records keyed `empcode`, `timein`, `timeout`, `date`, `type`.
   Expected `date`/`timein`/`timeout` format: `m/d/Y h:i:s A` (e.g. `05/01/2024 08:00:00 AM`).

There is **no cron/console command** — syncing is triggered only by hitting the HTTP endpoint.

### Coupling to `EmpTask`
A `WorkerLogs` row is tightly coupled to project-task rows (`EmpTask`) via
`EmpTask.worker_logs`. On every log create/update, `updateWorkerLogEmpTask()`/`updateEmpTask*()`
match EmpTasks whose `date` (day-only) equals the log's `loginDate` (day-only) and are still
`approved == null`, then set `approved = true` and `rendered_hours = assigned_hours`. Absence
generation runs the inverse (sets `approved = false`, `rendered_hours = 0`, `attendance = Absent`).

---

## 2. CORE ENTITIES (fields relevant to DTR)

### WorkerLogs (`App\Entity\WorkerLogs`, table `worker_logs`)
| field | type | notes |
|---|---|---|
| id | int AI | |
| user | Worker (FK, not null) | owning side of punch |
| type | string|nullable | 'IN'/'' etc. |
| loginDate | datetime nullable | the PUNCH-IN timestamp |
| logoutDate | datetime nullable | the PUNCH-OUT timestamp |
| worker_log_id | string nullable | original device `id` (dedupe key vs device) |
| overtime | float nullable | minutes of OT (computed) |
| overtime_approved | bool nullable | paid only when true |
| undertime | float nullable | minutes short of shift |
| attendance_status | AttendanceTypes nullable | e.g. "Present"/"Absent" |
| rendered_hours | float nullable | minutes actually worked (incl. OT) |
| empTasks | EmpTask[] | inverse |
| is_time_calculated | bool (not null) | guards recompute |
| created_at | datetime_immutable nullable | |
| employeeOvertimeRequests | EmployeeOvertimeRequest[] | inverse |
| dTRAdjutments | DTRAdjutments[] | inverse |

### Worker (`App\Entity\Worker`)
`id`, `workerId`, `firstname`, `lastname`, `position`, `workerDocs`, `photo`, `erName`,
`erContact`, `status`, `workerLog` (WorkerLogs[]), `empcode`, `emp_record` (EmployeeRecords?).
Link to employee is `Worker.emp_record` (EmployeeRecords). The **User** that owns the shift is
`Worker.emp_record.user`, and shift is `User.emp_shift` (Shifts) plus `User.is_straight_time` (bool).

### AttendanceTypes (`App\Entity\AttendanceTypes`)
`id`, `name` (e.g. "Absent", "Present"), `is_hours_rendered` (bool), `hours_provided` (float,
**unused anywhere**), `automated_attendance` (bool — marks the "present" type used by sync).
The sync/CSV code finds the "present" type via `findOneBy(['automated_attendance' => true])` and
the "absent" type via `findOneBy(['name' => 'Absent'])`.

### Shifts (`App\Entity\Shifts`)
`id`, `start_time` (TIME_MUTABLE), `end_time` (TIME_MUTABLE), `archived` (bool), `name`,
`users` (User[]), `lunch_break_duration` (float, minutes), `total_hours_minus_lunch` (float,
minutes), `days_of_week` (ARRAY of strings '1'..'7' = ISO weekday from `format('N')`).

### DTRAdjutments (`App\Entity\DTRAdjutments`) — NOTE the class-name typo "Adjutments"
`id`, `worker_logs` (WorkerLogs?), `emp_record` (EmployeeRecords?), `adjusted_date` (DATE_MUTABLE).
Represents a manual carry-over of a worker log's OT into a later payroll cut-off (see §7).

### EmployeeOvertimeRequest (`App\Entity\EmployeeOvertimeRequest`)
`id`, `emp_id` (EmployeeRecords), `worker_logs` (WorkerLogs), `status` (smallint: 0 pending,
1 approved, 2 rejected), `approved_by` (EmployeeRecords), `time_requested` (float — minutes),
`reason` (string).

### EmpTask (`App\Entity\EmpTask`)
`id`, `emp_project`, `task_desc`, `rendered_hours` (int), `date` (datetime), `archived`,
`approved` (bool|null), `assigned_hours` (float), `is_adjusted` (bool), `worker_logs` (WorkerLogs).

### SyncConnection (`App\Entity\SyncConnection`)
`id`, `username`, `password`, `dbname`, `host`. Only `id = 1` is ever read.


---

## 3. THE DTR PIPELINE & EXACT FORMULAS

### 3.1 Constants
```
DEFAULT_SHIFT_MINUTES   = 480          // minutes/day when no shift assigned (8h)
HARDCODED_LUNCH_DEDUCT  = 60           // minutes ALWAYS subtracted in sync/CSV calc, regardless of shift.lunch_break_duration
MINUTES_PER_DAY (pay)   = 480          // '8 * 60' in PayrollGenerationController
SECONDS_TRIM            = 60           // the "- 60" in totals = 1 hour shaved off (see bug §8)
OT_RATE_COLUMN          = payroll_profile.overtime_rate   // currency per OT hour
LATE_RATE_COLUMN        = payroll_profile.late_rate       // currency per undertime hour
```

### 3.2 Rendered / Overtime / Undertime computation (sync + CSV + straight_time)
All three code paths use the SAME `calcOvertime` / `calcUndertime` helpers:

```
totalMinutesDifference = diffMinutes(loginDate, logoutDate) - 60   // the "- 60" is a hardcoded lunch
rendered_hours   = totalMinutesDifference
overtime         = max(0, totalMinutesDifference - empShiftHours)         // empShiftHours = Shifts.total_hours_minus_lunch (or 480)
undertime        = max(0, empShiftHours - totalMinutesDifference)
```
where `empShiftHours = user.emp_shift.total_hours_minus_lunch` if a shift exists, else `480`.
`diffMinutes` = `($interval->days*24*60) + ($interval->h*60) + $interval->i` (absolute, `true`).

In `SyncWorkerController::syncWorkerLogsPerday` an EXTRA step zeroes seconds:
```
$newLogIn ->setTime(H, i, 0);  $newLogOut ->setTime(H, i, 0);
$interval = $newLogIn->diff($newLogOut, true);
$totalMinutesDifference = diffMinutes - 60;
```

### 3.3 Straight-time variant (`PATCH /api/straight_time/{id}`)
For users with `is_straight_time = true` (lunch NOT deducted from pay), the endpoint ADDS the
lunch duration back to rendered hours but NOT to overtime:
```
empShiftwithLunch = user.emp_shift.total_hours_minus_lunch
lunch = user.emp_shift.lunch_break_duration
diff  = diffMinutes(login, logout) - 60
undertime = calcUndertime(diff + lunch, empShiftwithLunch)
overtime  = calcOvertime(diff, empShiftwithLunch)        // lunch NOT added here
rendered  = diff + lunch
```
(The `update_attendance` path also adds `lunch/100` or `lunch/60` to rendered when straight-time,
a fragile/confusing branch — see §8.)

### 3.4 Absence detection (`checkAbsences` in Manpower / `CheckEmpDtrController`)
For a worker, find latest log, derive a **semi-monthly cut-off** (`getCurrentCutoffDateRange`):
```
if day <= 15 : range = [Y-m-01 00:00:00 , today 23:59:59]
else         : range = [Y-m-16 00:00:00 , today 23:59:59]
```
For each calendar day in range: if no `WorkerLogs` login on that day AND the day's ISO-weekday
(`format('N')` → '1'..'7') is in `user.emp_shift.days_of_week` → create an "Absent" log:
`rendered_hours=0, undertime=0, overtime=0, attendance='Absent', is_time_calculated=true`.
(Manpower's `createNewAbsentWorkerLogs` sets undertime=0; the dead `CheckEmpDtrController`
counterpart sets undertime=480 — they disagree. Manpower's is the live one.)

### 3.5 Payroll consumption (PayrollGenerationController)
```
totalRenderedMinutes += log.rendered_hours
totalApprovedOvertime += log.overtime * (log.overtime_approved ? 1 : 0)
totalOvertime        += log.overtime
totalUndertime       += log.undertime

totalRenderedMinutes -= totalOvertime        // OT is removed so it isn't paid twice as regular

total_calc_overtime   = (totalApprovedOvertime / 60) * overtime_rate
total_calc_undertime  = (totalUndertime       / 60) * late_rate
totalRenderedDays     = round(totalRenderedMinutes / 480, 2)

salary = daily_rate*totalRenderedDays + allowance/2 + total_calc_overtime - total_calc_undertime + taxable_adj
```
**Unapproved OT is NOT paid** (only `overtime_approved` count). DTR adjustments add OT via
`getOvertimeInDTRAdjustments()` (which sums `worker_logs.overtime` for adjustments in range —
NOTE: it does NOT check `overtime_approved`, so adjustment OT is always paid — inconsistent with
the direct path).

### 3.6 Night differential
**NOT IMPLEMENTED ANYWHERE.** No controller, entity, or config references a night-differential
window. `grep` for night/NIGHT returns nothing. DTR/OT and payroll ignore any 22:00–06:00 premium.

---

## 4. SyncWorkerController (`/sync/worker`)
Class has NO `#[Route]` prefix; single route. Resolves `Worker`→`EmployeeRecords` via a CSV
(`public/excel_files/empfiles.csv`) by fuzzy name match (`compareNames`, threshold 0.7) to set
`empcode`/`emp_record`. This matching is approximate and can mis-link workers.

### 4.1 Route
- `GET|POST /sync/worker` (`name: app_sync_worker`) → `syncLogs(CsvReader)`
  - No `methods` arg → Symfony allows any method. No auth firewall applies (path `/sync/*` is not
    matched by `^/api` firewall) → **publicly callable, yet mutates data** (see §8).
  - Logic: `fetchConnectionParameters()` reads `SyncConnection id=1` → build PDO →
    `syncWorkers($pdo)` (copy `worker` rows) → `syncWorkerLogsPerday($pdo)`.
  - Returns `{status: "success"}` 202 on success; 400 if no connection; 500 on PDOException.

### 4.2 `syncWorkerLogsPerday` — the pairing algorithm
1. Reads device `worker_logs` ordered by `login_date DESC LIMIT 1`; takes `latest_date` (date only).
2. Pulls all device rows with `login_date > latest_date` (so the last synced day is **re-pulled
   every run** — no local watermark; potential duplicate re-processing).
3. Builds `workerMap[user_id] => Worker`.
4. For each device row:
   - If a local `WorkerLogs` exists with `worker_log_id = device.id` (dedupe by device id):
     recompute rendered/OT/undertime **only if `!is_time_calculated`**; set `attendance_status`
     to the `automated_attendance=true` type; update type/login/logout/user; call `updateEmpTask`.
   - Else: `ifExistingLogs = searchIfExisitingDate(loginDate Y-m-d, workerId)`; if none, create a
     new `WorkerLogs` (`is_time_calculated=false`) and call `updateEmpTask`, flush inside loop.
5. Final flush + `entityManager->clear()`.

**Pairing model:** the device DB already stores paired IN/OUT in one row (`login_date`,
`logout_date`). There is **no in-app IN/OUT matching algorithm** — the app assumes the device
pre-pairs punches. Odd punch counts, missing OUT, and duplicate punches are handled entirely
upstream by the device DB. Within the app, a missing `logout_date` means
`$loginDate && $logoutDate` is false → **no time calculation**, `is_time_calculated` stays false,
rendered/OT/undertime remain null. Overnight shifts crossing midnight work only if the device
writes `logout_date` on the next calendar day (diff is absolute so sign doesn't matter).

---

## 5. AttendanceController (`/api/attendance-types`) — class prefix NONE
Manages `AttendanceTypes` reference data. No auth checks beyond the global `^/api` firewall (any
authenticated user). Serialization group `all_worker_logs` / `worker_logs`.

### 5.1 Routes
| method | path | name | method |
|---|---|---|---|
| GET | `/api/attendance-types` | get_attendance_types | getAttendanceTypes() |
| GET | `/api/attendance-types/{id}` | get_attendance_type | getAttendanceType(int $id) |
| PUT | `/api/attendance/update/{id}` | update_attendance | updateAttendance($id, Request) |

### 5.2 `getAttendanceTypes` (GET /api/attendance-types)
- Resp 200: `{message, attendance_types:[<AttendanceTypes via group 'all_worker_logs'>]}`.
- 500 on exception.
### 5.3 `getAttendanceType` (GET /api/attendance-types/{id})
- 404 `{error:"Attendance type not found"}` if missing.
- 200 `{message, attendance_type:{...}}`.
### 5.4 `updateAttendance` (PUT /api/attendance/update/{id})
- Body keys (all optional, set only if present): `name`, `is_hours_rendered`
  (maps to `setHoursRendered`), `hours_provided` (`setHoursProvided`), `automated_attendance`.
- 404 if not found. Validates via Validator; 400 with `(string)$errors` on failure.
- Persists; returns serialized entity (group `worker_logs`) as raw JSON (200). `hours_provided`
  is **never read** by any DTR logic.

---

## 6. DTRController (`/api/dtr/count`) — stub
Class prefix NONE. Single useless route.
- `GET|POST /api/dtr/count` (`name: app_dtr_count`) → `countDTR()`
  - Returns `{message:"Welcome to your new controller!", path:"src/Controller/DTRController.php"}`.
  - No DB access, no parameters. Dead/placeholder endpoint.

---

## 7. DTRAdjustmentsController (`/api/dtr-adjustments`)
Class prefix `/api/dtr-adjustments`. Manages `DTRAdjutments` (OT carry-over rows). No auth checks.

### 7.1 Routes
| method | path | name | method |
|---|---|---|---|
| GET | `/api/dtr-adjustments/list` | dtr_adjustments_list | list() |
| POST | `/api/dtr-adjustments/create` | dtr_adjustments_create | create(Request) |
| GET | `/api/dtr-adjustments/find/{id}` | dtr_adjustments_show | show(int $id) |
| PUT | `/api/dtr-adjustments/update/{id}` | dtr_adjustments_update | update(Request, int $id) |
| DELETE | `/api/dtr-adjustments/delete/{id}` | dtr_adjustments_delete | delete(int $id) |

### 7.2 `list` (GET)
Returns a flat array of `{id, worker_logs_id, emp_record_id, adjusted_date(Y-m-d)}` for all rows.

### 7.3 `create` (POST)
Body keys: `emp_record_id` (required), `workerlogs_id` (required).
1. Resolve `EmployeeRecords` by `emp_record_id` → 400 if missing.
2. Resolve `WorkerLogs` by `workerlogs_id` → 400 if missing.
3. `latest_payroll_date = PayrollGroupsRepository::findLatestPayrollGroup()`. Must exist → 400 if null.
4. `latestDate = latest_payroll_date->getDateEnd()`; **then `$latestDate->modify('+1 day')`**.
   ⚠️ `getDateEnd()` returns the SAME `DateTime` object Doctrine loaded; `modify()` mutates it
   in place, so the PayrollGroups row's own `date_end` is now changed in the identity map and may
   be persisted/flushed unintentionally (see §8, DateTime-mutation bug).
5. Create `DTRAdjutments{workerLogs, empRecord, adjustedDate=latestDate}`, flush.
6. 201 `{status:"DTR Adjustment created!"}`.
*Effect on payroll:* `PayrollGenerationController::getOvertimeInDTRAdjustments()` later sums the
linked `worker_logs.overtime` for adjustments whose `adjusted_date` falls in the payroll range and
adds `(sum/60)*overtime_rate` to pay. **Approval is NOT checked** for adjustment OT (unlike direct
log OT).

### 7.4 `show` (GET /find/{id})
200 `{id, worker_logs_id, emp_record_id, adjusted_date}` or 404.

### 7.5 `update` (PUT /update/{id})
Body key `adjusted_date` → `setAdjustedDate(new \DateTime($data['adjusted_date']))`. 404 if missing. 200 `{status}`.

### 7.6 `delete` (DELETE /delete/{id})
Removes row. 404 if missing. 200 `{status}`.

*No audit of who created/adjusted, no approval workflow — creation is immediate and affects pay.*

---

## 8. DTRReportController (`/api/dtr-filter-*`) — REPORTS (task/manpower aggregation)
Class prefix NONE. Four POST endpoints aggregate `EmpTask` rendered hours + overtime. No auth beyond
global firewall. All require valid JSON or 400. Date range format string is `"<start> to <end>"`
(space-`-`-`to`-space), parsed by `explode(' to ', $dateRange)`. **Inconsistent end-of-day
handling** between endpoints (see §8 bugs).

| method | path | name | method |
|---|---|---|---|
| POST | `/api/dtr-filter-by-task` | dtr_filter_by_task | getRequiredData(Request) |
| POST | `/api/dtr-filter-by-project` | dtr_filter_by_project | filterDTRByProject(Request) |
| POST | `/api/dtr-filter-by-activity` | dtr_filter_by_activity | filterDTRByTask(Request) |
| POST | `/api/dtr-filter-by-emp` | dtr_filter_by_emp | filterDTRByEmployee(Request) |

### 8.1 `getRequiredData` (POST /api/dtr-filter-by-task)
Body `project_id` (required, else 404 "Employee Project not found"). Returns unique task
descriptions (`id`, `description`) for the project's `EmployeeProjects→EmpTasks`.

### 8.2 `filterDTRByProject` (POST /api/dtr-filter-by-project)
Body `project_id` (required), `date_range` (`"Y-m-d to Y-m-d"`). `start`/`end` set to `00:00:00`.
For each project (or all), sums `EmpTask.rendered_hours` per `task_desc` within range; converts
minutes→man-days via `convertMinuteToMandays` (`minutes/480`). Returns
`[{name, tasks:[{description, total_rendered_time}]}]`. **No overtime included here.**

### 8.3 `filterDTRByTask` (POST /api/dtr-filter-by-activity)
Body `project_id`, `date_range`, `task_desc` (filter; exact match or 'all'). `end` set to `23:59:59`.
Groups by `description → employee → date`. Per cell adds `rendered_time` and, if the task's
`WorkerLogs` exists AND `workerLogs.isOvertimeApproved()`, adds `overtime`. Returns
`[{name, tasks:[{description, employees:[{employee, date, total_rendered_time, total_overtime}]}]}]`.
Has a duplicated `taskDescFilter` block (copy-paste).

### 8.4 `filterDTRByEmployee` (POST /api/dtr-filter-by-emp)
Body `employee_id` (required, 400 if null), `date_range`, `task_desc` (substring via `stripos`).
`end` set to `23:59:59`. Same grouping; `overtime` added only when approved. Returns same shape.

`convertMinuteToMandays`:
```
totalMandays = $minutes ? $minutes/480 : 0;
```

---

## 9. CheckEmpDtrController (`/check/emp/dtr`)
Class prefix NONE, single route, **NO `methods`** (any method) and **NOT under `/api`** → not
covered by the JWT firewall → effectively public, yet it mutates `EmpTask` rows.

- `GET|POST /check/emp/dtr` (`name: app_check_emp_dtr`) → `check_dtr()`
  - Reads latest `WorkerLogs.loginDate`, derives semi-monthly cut-off (same as §3.4).
  - For each `Worker` with `emp_record` (via `WorkerRepository::findAllWithEmpRecord()`): for each
    calendar day in range, if no login that day and weekday ∈ shift `days_of_week`, calls
    `updateEmpTask($worker, $currentDate)` (sets matching EmpTasks `approved=false`,
    `rendered_hours=0`).
  - ⚠️ `check_dtr()` uses `array_map(...)` with a closure that has **no `return`**, so it returns
    an array of `null`; the `{data: ...}` is meaningless. Also calls `$this->entityManager->clear()`
    **inside** the loop body (`updateEmpTask`) → detaches managed entities mid-iteration → subsequent
    lazy access on detached `Worker`/`EmployeeRecords` can throw.
  - 200 `{message:"Worker absence data", data:[...nulls...]}`.

---

## 10. ShiftsController (`/api/shifts`)
Class prefix NONE. All mutating routes call `UserAccessValidation::validateUserAccess($request,
'shifts', <add|edit|delete|view>)` → 401/403 on failure.

| method | path | name | method |
|---|---|---|---|
| GET | `/api/shifts` | view_shifts | viewShifts(Request) |
| POST | `/api/create/shifts` | add_shift | addShift(Request) |
| PUT | `/api/shifts/{id}` | update_shift | updateShift(Request, int $id) |
| PATCH | `/api/shifts/archive/{id}` | archive_shift | archiveShift(Request, int $id) |

### 10.1 `viewShifts` (GET /api/shifts)
Returns `findByNotArchived()` mapped to:
`{id, name, start_time(H:i:s), end_time(H:i:s), lunch_duration, days_of_week, total_hours}`. 200.

### 10.2 `addShift` (POST /api/create/shifts)
Body: `name`(opt), `start_time`(req, `H:i:s`/`H:i`→`new \DateTime`), `end_time`(req),
`lunch_duration`(req), `week_sched`(req = days_of_week array).
- 400 if start/end/week_sched missing.
- Computes `totalMinutesWorked = calculateTotalMinutesWorked(start, end, lunch)` and stores on entity.
- Persists; 201 `{message, shift:{id,name,start_time,end_time,total_hours_worked}}`.

`calculateTotalMinutesWorked(DateTime $start, $end, ?float $lunch)`:
```
if ($start && $end && $lunch !== null) {
    $interval = $start->diff($end);
    $total = ($interval->days*24*60) + ($interval->h*60) + $interval->i;
    $total -= $lunch;
    return $total;
}
return 0;   // returns 0 if lunch is null → total hours lost!
```

### 10.3 `updateShift` (PUT /api/shifts/{id})
Body optional: `name`, `week_sched`, `start_time`, `end_time`, `lunch_duration`.
⚠️ If `end_time` NOT supplied it falls back to `else { $end_time = $shift->getStartTime(); }`
(setting end = start) → negative total hours stored. Same missing-lunch → 0 bug.
Persists; 200.

### 10.4 `archiveShift` (PATCH /api/shifts/archive/{id})
Sets `archived=true`. 404 if missing; 200.

### 10.5 Shift assignment
Shift is assigned to a **User** (not Worker) via `UsersController::update` (`PATCH/PUT /api/user/{id}`)
body key `emp_shift` → `user.setEmpShift(Shifts)`. `is_straight_time` assignment is commented out in
that controller (currently cannot be set via API despite the field existing).

---

## 11. EmployeeOvertimeRequestController (`/api/overtime_requests`)
Class prefix `/api/overtime_requests`. No auth checks.
Status values in `EmployeeOvertimeRequest.status`: **0 = pending, 1 = approved, 2 = rejected**
(smallint). `time_requested` is stored in **minutes** but the UI text formats it as `H:MM`.

| method | path | name | method |
|---|---|---|---|
| GET | `/api/overtime_requests/list` | list_overtime_requests | list() |
| POST | `/api/overtime_requests/create` | create_overtime_request | create(Request) |
| GET | `/api/overtime_requests/find/{id}` | show_overtime_request | show(int $id) |
| GET | `/api/overtime_requests/find-by-emp/{id}` | show_overtime_request | showByEmpId(int $id) |
| PUT | `/api/overtime_requests/update/{id}` | update_overtime_request | update(Request, int $id) |
| PUT | `/api/overtime_requests/update-status/{id}` | update_overtime_request_status | updateStatus(Request, int $id) |
| DELETE | `/api/overtime_requests/delete/{id}` | delete_overtime_request | delete(int $id) |

⚠️ **Route-name collision:** both `find/{id}` and `find-by-emp/{id}` declare
`name: show_overtime_request`. Symfony `RouteCollection::add()` overwrites by name, so only ONE
survives in the router (the last registered wins); the other becomes unreachable by name (path
still matches on URL, so HTTP works, but URL-generation by name is broken). Same anti-pattern as in
LeaveRequestController (out of scope).

### 11.1 `list` (GET)
Maps every request to:
```
{id, emp_id, hours_requested("H:MM"), reason,
 worker_logs, worker_logs_date(Y-m-d), worker_logs_overtime, status,
 approved_by:"Last, First"}
```
`hours_requested` formatting:
```
$hours = intdiv($totalMinutes, 60); $minutes = $totalMinutes % 60;
$hoursRequested = sprintf('%d:%02d', $hours, $minutes);
```

### 11.2 `create` (POST)
Body: `emp_id`(req), `worker_logs`(req, the WorkerLogs id), `reason`(default ""),
`hours_requested`(default 0). Sets `status=0`. Links `EmployeeRecords` + `WorkerLogs`. Persists.
201. ⚠️ `time_requested` (hours_requested) is stored but **never used in payroll** — payroll reads
`WorkerLogs.overtime`, not the request. The request is effectively an approval envelope only.

### 11.3 `show` / `showByEmpId` (GET)
Single / by-employee arrays with same shape. `find-by-emp` returns `[]` (empty array, 200) when none.

### 11.4 `update` (PUT /update/{id})
Body `hours_requested`, `reason`. Overwrites those two fields only. 404 if missing. 200.

### 11.5 `updateStatus` (PUT /update-status/{id}) — THE APPROVAL WORKFLOW
Body: `status` (1|2), `user_id` (the approver's User id).
1. Load request; 404 if missing.
2. `$workerLogs = $request->getWorkerLogs();` (an entity) → then
   `$workerLogs = repository->find($workerLogsId);` — Doctrine `find()` accepts an entity and
   extracts its id, so this works, but if `getWorkerLogs()` is null → `find(null)` throws
   (500). Also the `$data['user_id']` is read with no `??` guard → undefined-index notice/500 if
   absent.
3. If `status == 1` → `workerLog->setOvertimeApproved(true)`; if `2` → `setOvertimeApproved(false)`.
4. Resolve approver: `EmployeeRecords::findOneBy(['user' => $data['user_id']])` → 404 if missing;
   `setApprovedBy(...)`.
5. `setStatus((int)$status)`; flush. 200.

**Who approves / chain:** single-level only. Any authenticated caller can approve (no role gate in
this controller; the shift controller gates by submodule but OT does not). No notification is sent
on OT approval. There is **no minimum-OT threshold** and **no rest-day/holiday OT special rate** —
all OT uses `payroll_profile.overtime_rate` uniformly regardless of rest day/holiday.

### 11.6 `delete` (DELETE)
Removes row. 404 if missing. 200.

> Also relevant: `WorkersController` exposes two OT endpoints that bypass the request entity and
> flip `WorkerLogs.overtime_approved` directly (see §13).

---

## 12. WorkersController (`/api/worker-overtime/*`) — direct OT & attendance overrides
Class prefix NONE. No auth checks.

| method | path | name | method |
|---|---|---|---|
| PATCH | `/api/worker-overtime/approve/{id}` | approve_worker_ot | approveWorkerOvertime($id, Request, WorkerLogsRepository) |
| PATCH | `/api/worker-overtime/deny/{id}` | deny_worker_ot | denyWorkerOvertime($id, Request, …) |
| POST | `/api/worker-overtime/update_attendance/{id}` | update_worker_attendance | updateWorkerLogsByAttendance($id, Request, …) |
| PATCH | `/api/straight_time/{id}` | straight_time | addLunchBreakTimeToRendered($id, Request, …) |

### 12.1 `approveWorkerOvertime` (PATCH /api/worker-overtime/approve/{id})
`WorkerLogs` by id → `setOvertimeApproved(true)`. 404 if missing. 200 `{message:"Overtime approved."}`.

### 12.2 `denyWorkerOvertime` (PATCH /api/worker-overtime/deny/{id})
Same, sets `overtime_approved=false`. 200 `{message:"Overtime denied."}`.

### 12.3 `updateWorkerLogsByAttendance` (POST /api/worker-overtime/update_attendance/{id})
Body `attendance_id` (AttendanceTypes id, required). Loads `WorkerLogs` by id.
- If `attendanceType.isHoursRendered()`:
  `adjusted = user.emp_shift.total_hours_minus_lunch` (for straight-time users, adds
  `lunch/100` or `lunch/60` — a confusing unit branch). `setRenderedHours(adjusted)`; for each
  linked EmpTask: `setRenderedHours(assigned_hours); setApproved(true)`.
- Else: `setRenderedHours(0)`; EmpTasks `setRenderedHours(0); setApproved(false)`.
- `setAttendanceStatus(attendanceType)`; flush. 200.
⚠️ The loop contains dead code (`$renderedHours`, `$newRenderedHours`) and the lunch math
(`/100` vs `/60`) is suspicious/likely buggy.

### 12.4 `addLunchBreakTimeToRendered` (PATCH /api/straight_time/{id})
Straight-time recompute (formula in §3.3). Flush. 200.

---

## 13. ManpowerController — DTR-relevant routes (manual punch upload + reports)
(Selected routes only; full file is 2598 lines.) Class prefix NONE. Auth: global `^/api` firewall
only (any authenticated user) for `/api/*`; the worker_logs/create is under `/api`.

| method | path | name | purpose |
|---|---|---|---|
| POST | `/api/worker_logs` | view_worker_logs | list WorkerLogs in date range |
| POST | `/api/worker/{id}` | view_worker_logs_id | WorkerLogs for one worker + date range |
| POST | `/api/emp-tasks-dtr/create` | create_emp_dtr_task | create EmpTask(s) (DTR-linked) per day range |
| POST | `/api/worker_logs/create` | create_worker_logs | **bulk manual punch upload** |
| GET | `/api/workerlogs/get-latest-time/{id}` | get_latest_log_time | latest log timestamp |

### 13.1 `createWorkerLogs` (POST /api/worker_logs/create) — manual punch intake
Body: JSON **array** of `{empcode, timein, timeout, date, type?}` (format `m/d/Y h:i:s A`).
- Per row, in a DB transaction (`beginTransaction`/`commit`/`rollback`):
  - Skip row if no `empcode`, or empty timein/timeout/date, or unparseable datetime.
  - Resolve Worker by `empcode`; if none, try `EmployeeRecords.employee_code`, else create a new
    Worker (`workerId = hash('sha256', empcode)`).
  - Dedupe: `findOneBy(['user'=>worker, 'loginDate'=>loginDateTime])` → skip if exists.
  - Compute `empShiftHours` (shift total or 480); compute rendered/OT/undertime with the SAME
    `diffMinutes - 60` formula; set `attendance_status` = `automated_attendance=true` type;
    `is_time_calculated=true`.
  - Validate; persist; commit; call `updateWorkerLogEmpTask`; (notification "uploaded DTR").
- After loop, for each worker call `checkAbsences($worker)` (absence generation, §3.4).
- 201 `{message:"Worker logs created successfully."}` (or 500 with exception message mid-loop).
⚠️ The dedupe key `loginDate` is the **full datetime**; absence rows created with `loginDate` at
`00:00:00` will NOT collide with a later real punch (different time) → duplicate "absent" + real
log can coexist.

### 13.2 `view_worker_logs` / `view_worker_logs_id` (POST)
Body `start_date`,`end_date` (Y-m-d). `end` defaults to `start 23:59:59` if omitted. Returns
serialized `WorkerLogs` (groups `all_worker_logs` / `worker_logs`) + counts. No pagination.

### 13.3 `create_emp_dtr_task` (POST /api/emp-tasks-dtr/create)
Body `project_id`,`employee_id`,`start_date`,`end_date`,`task_desc`,`assigned_hours`.
Auto-creates `EmployeeProjects` if none; for each day in `[start,end]` inclusive creates an
`EmpTask{date, task_desc, assigned_hours}`. 201. (This is how DTR task rows that later get paired
to WorkerLogs are seeded.)

---

## 14. RULES SUMMARY (re-implementation reference)

### 14.1 Shift definition
- Stored in `Shifts`: `start_time`, `end_time` (TIME only), `lunch_break_duration` (minutes),
  `total_hours_minus_lunch` (minutes, precomputed = `diff(start,end) - lunch`), `days_of_week`
  (array of '1'..'7' ISO weekdays), `archived`, `name`.
- Assigned to **User** via `user.emp_shift` (UsersController). `is_straight_time` exists but its
  setter is commented out in the API.
- **No grace period** concept anywhere. Late detection is implicit: `undertime = shiftMinutes -
  renderedMinutes` (so "late arrival" and "early departure" both just reduce rendered and increase
  undertime). There is no separate late-minutes figure.
- **Break handling:** lunch is NOT a punched entity. In the sync/CSV path a **hardcoded 60 minutes**
  is always subtracted (`- 60`) regardless of `lunch_break_duration`. `total_hours_minus_lunch` is
  used only as the OT/undertime baseline (`empShiftHours`). For straight-time users, lunch is added
  back into `rendered_hours` but not into OT.

### 14.2 IN/OUT pairing
- The app does **not** pair punches. The external device DB stores one row per paired IN/OUT
  (`login_date`,`logout_date`). The app ingests pre-paired rows.
- Odd punch counts / missing OUT: if `logout_date` is null, no time calc runs; `rendered_hours`,
  `overtime`, `undertime` stay null. The row is treated as a present-but-uncalculated punch until a
  logout arrives (or never).
- Duplicate punches: prevented only by `worker_log_id` (device id) dedupe on sync and by full
  `loginDate`+`user` dedupe on manual upload.
- Overnight/graveyard: works only if device writes `logout_date` on the next day; diff is absolute.

### 14.3 Rendered / Late / Undertime / Absence / Half-day
- `rendered_hours = diffMinutes(login,logout) - 60` (minutes, includes OT).
- `overtime = max(0, rendered - shiftMinutes)`; `undertime = max(0, shiftMinutes - rendered)`.
- `shiftMinutes = user.emp_shift.total_hours_minus_lunch ?? 480`.
- **Absence:** generated by `checkAbsences` for any scheduled weekday (per `days_of_week`) in the
  semi-monthly cut-off with no WorkerLogs login; creates an "Absent" log `rendered=0, undertime=0,
  overtime=0`. (Half-day is a LEAVE concept, out of scope here; Attendance/DTR has no half-day.)

### 14.4 Overtime
- Computed in minutes as above and stored on `WorkerLogs.overtime`.
- **Approval required to be PAID:** payroll counts only `overtime * (overtime_approved?1:0)`.
  Unapproved OT → not paid. Approval set via `WorkersController` PATCH endpoints or
  `EmployeeOvertimeRequest::updateStatus` (status 1 → approved).
- `EmployeeOvertimeRequest.time_requested` is stored but unused by payroll (decoupled).
- No min OT threshold, no rest-day/holiday differential, single `overtime_rate` for all OT.
- DTR adjustments' OT (`getOvertimeInDTRAdjustments`) is paid **without** an approval check.

### 14.5 Night differential
**Not implemented.** No window, no rate, no counting anywhere in the codebase.

### 14.6 DTR adjustments
- `DTRAdjutments` = carry a WorkerLogs' OT into a later payroll cut-off (its `adjusted_date` is set
  to `latestPayrollGroup.date_end + 1 day`). No approval workflow, no auditor field, no creator
  tracking. On payroll, summed into OT pay (unapproved).

### 14.7 Date/time formats & timezone
- Formats: `'Y-m-d'`, `'Y-m-d H:i:s'`, `'H:i:s'`, device `'m/d/Y h:i:s A'`, man-day date-range
  string `'Y-m-d to Y-m-d'`.
- Timezone: `date_default_timezone_set('Asia/Manila')` is called in `SyncWorkerController` and
  `CheckEmpDtrController` constructors (side-effect on global TZ). `AuditLog` and entity setters use
  explicit `new DateTimeZone('Asia/Manila')`. Doctrine stores datetimes as-is (no TZ conversion
  configured). Risk: global TZ mutation + reliance on server TZ for stored timestamps.
- **DateTime mutation bugs:** (1) `DTRAdjustmentsController::create` mutates
  `PayrollGroups.date_end` in place via `modify('+1 day')`; (2) `WorkersController::straight_time`
  and `SyncWorkerController` mutate `loginDate`/`logoutDate` in place (only safe because the same
  object is then persisted).

### 14.8 List/filter/pagination conventions
- List endpoints generally return **all rows** (no limit/offset/page params) except where noted.
  `ManpowerController::viewWorker` accepts `page`/`limit` query params but ignores them
  (`limit` default 3000, effectively all). `view_worker_logs` uses `start_date`/`end_date` body
  keys (no pagination). Date ranges use `BETWEEN` with `00:00:00`–`23:59:59` (except
  `dtr-filter-by-project` which uses `00:00:00`–`00:00:00`, excluding same-day tasks — bug).

---

## 15. KNOWN HACKS / WEAK SPOTS / BUGS

1. **Public, data-mutating endpoints.** `/sync/worker` and `/check/emp/dtr` are not under `/api`,
   so they bypass the JWT firewall; both mutate `WorkerLogs`/`EmpTask`. Anyone who can reach the
   host can trigger syncs/absence writes.
2. **Hardcoded `- 60` lunch.** `diffMinutes - 60` ignores `Shifts.lunch_break_duration`; a 30- or
   90-min break is always counted as 60. This skews rendered/OT/undertime for every punch.
3. **`total_hours_minus_lunch` becomes 0 when lunch null** (`calculateTotalMinutesWorked` returns 0
   if `$lunch === null`), and `updateShift` keeps old start when `end_time` omitted → negative hours.
4. **Route-name collisions** (`show_overtime_request` twice; `app_leave_request_update` twice in
   Leave controller) — `RouteCollection::add` overwrites by name; URL generation by name breaks.
5. **`entityManager->clear()` inside `updateEmpTask` loop** (`CheckEmpDtrController`) → detaches
   entities mid-iteration; subsequent lazy loads can throw.
6. **No local sync watermark.** `syncWorkerLogsPerday` re-pulls `login_date > latestDate` so the
   last synced day is reprocessed every run; relies on device-id dedupe to avoid duplicates.
7. **Absence vs real-punch collision.** Absence log uses `loginDate 00:00:00`; a later real punch
   (different time) does not match the dedupe key → both an "Absent" row and the real row coexist;
   payroll may double count or zero the day inconsistently.
8. **`check_dtr()` returns array of nulls** (`array_map` closure has no return) — response `data`
   is meaningless; logic is side-effect only.
9. **OT request `time_requested` unused.** Approval envelope decoupled from actual `WorkerLogs`
   overtime; an approver can approve an OT request while the underlying log's `overtime` value is
   anything.
10. **DTR-adjustment OT paid without approval** while direct-log OT requires `overtime_approved` —
    inconsistent pay rules.
11. **N+1 / loop queries.** `updateEmpTask`/`checkAbsences` issue per-worker and per-task queries;
    `SyncWorkerController::updateEmpTask` loops `EmployeeProjects` and `EmpTasks` issuing queries
    inside loops; `PayrollGenerationController::createPayrollPerEmployee` loops employees with
    per-employee repository calls.
12. **String date comparisons.** `EmpTask.date` compared with `==` after `setTime(0,0,0)`;
    `searchIfExisitingDate` uses `LIKE 'Y-m-d%'` (string prefix) rather than real date range.
13. **Off-by-one / end-of-day inconsistency.** `dtr-filter-by-project` sets `end = 00:00:00`
    (excludes same-day tasks) while sibling endpoints use `23:59:59`. `convertMinuteToMandays`
    divides by 480 (8h) even though workday may be 7h etc.
14. **Hardcoded IDs / values.** `SyncConnection id=1`; `HRS` department code in leave (out of
    scope); `lunch/100` vs `lunch/60` magic math; `'Absent'` name lookups (fail if renamed);
    `automated_attendance=true` must be unique or attendance is null.
15. **No transactions on sync/adjustment create** beyond manual-upload path; `DTRAdjustments::create`
    and report endpoints have no `beginTransaction`.
16. **`updateStatus` fragility.** `find($workerLogsId)` where `$workerLogsId` may be an entity or
    null → 500; `$data['user_id']` read without guard.
17. **`hours_provided` on AttendanceTypes is dead** — set but never read.
18. **Approval authorization absent** on OT approve/deny and OT request status — any authenticated
    user can approve OT (no role/submodule gate).
19. **`is_straight_time` cannot be set via API** (setter call commented out in UsersController)
    though the straight-time computation depends on it.
20. **Mutable DateTime side effects** — see §14.7; global `date_default_timezone_set` in
    constructors is a hidden global state change.

---

## 16. REIMPLEMENTATION CHECKLIST (minimal faithful port)
- [ ] External device DB via `sync_connection` (id=1): read `worker` + `worker_logs`
      (`id,user_id,login_date,logout_date,type`).
- [ ] Ingest → `WorkerLogs{user,worker_log_id,loginDate,logoutDate,type}`.
- [ ] Compute `rendered = diffMinutes - 60`; `overtime = max(0,rendered-shiftMin)`;
      `undertime = max(0,shiftMin-rendered)`; `shiftMin = user.emp_shift.total_hours_minus_lunch ?? 480`.
- [ ] `attendance_status` = AttendanceTypes where `automated_attendance=true` for present,
      `name='Absent'` for absence.
- [ ] Absence: semi-monthly cut-off from latest log; for each scheduled weekday w/o login create
      Absent log (rendered=undertime=overtime=0).
- [ ] Pair EmpTask by day-equality when `approved===null`: set approved + rendered=assigned_hours.
- [ ] OT approval flips `WorkerLogs.overtime_approved`; payroll pays only approved OT at
      `overtime_rate` = (approvedOTmin/60)*rate; subtract OT from rendered before day conversion.
- [ ] DTR adjustments shift OT to next cut-off (`date_end+1d`); summed (unapproved) into pay.
- [ ] Shifts: start/end/lunch/days_of_week/total; assign to User; no grace, no night diff.
- [ ] Fix the `-60` to use `lunch_break_duration`; fix end-of-day range; add auth + transactions.
