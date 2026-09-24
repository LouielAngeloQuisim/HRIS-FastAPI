# Architecture Map (generated, do not hand-edit)
Generated: 2026-09-24, from commit 4cc67e8
Regenerate this file with `bash scripts/gen-map.sh` rather than editing it by hand.

## Backend routes (`/api/*`): 225 endpoints in 39 groups

Grouped by top-level prefix. Format: `METHOD path  [perms: module:action]`.
No `[perms]` tag means the route has no `require_permission` dependency:
either auth/public endpoints, template demo resources (items, login flow),
or routes protected by the route_policy whitelist instead of RBAC modules.

### `/api/v1/audit-log` (2 routes)

- `GET /api/v1/audit-log/`  `[perms: audit:view]`
- `GET /api/v1/audit-log/{log_id}`  `[perms: audit:view]`

### `/api/v1/blocks` (5 routes)

- `GET /api/v1/blocks/`  `[perms: projects:view]`
- `POST /api/v1/blocks/`  `[perms: projects:add]`
- `DELETE /api/v1/blocks/{obj_id}`  `[perms: projects:delete]`
- `GET /api/v1/blocks/{obj_id}`  `[perms: projects:view]`
- `PATCH /api/v1/blocks/{obj_id}`  `[perms: projects:edit]`

### `/api/v1/categories` (5 routes)

- `GET /api/v1/categories/`  `[perms: category:view]`
- `POST /api/v1/categories/`  `[perms: category:add]`
- `DELETE /api/v1/categories/{obj_id}`  `[perms: category:delete]`
- `GET /api/v1/categories/{obj_id}`  `[perms: category:view]`
- `PATCH /api/v1/categories/{obj_id}`  `[perms: category:edit]`

### `/api/v1/daily-time-records` (7 routes)

- `GET /api/v1/daily-time-records/`  `[perms: daily_time_record:view]`
- `POST /api/v1/daily-time-records/`  `[perms: daily_time_record:add]`
- `DELETE /api/v1/daily-time-records/{obj_id}`  `[perms: daily_time_record:delete]`
- `GET /api/v1/daily-time-records/{obj_id}`  `[perms: daily_time_record:view]`
- `PATCH /api/v1/daily-time-records/{obj_id}`  `[perms: daily_time_record:edit]`
- `POST /api/v1/daily-time-records/{obj_id}/approve-overtime`  `[perms: daily_time_record:edit]`
- `POST /api/v1/daily-time-records/{obj_id}/reject-overtime`  `[perms: daily_time_record:edit]`

### `/api/v1/dashboard` (1 routes)

- `GET /api/v1/dashboard/`  `[perms: emp_list:view]`

### `/api/v1/departments` (5 routes)

- `GET /api/v1/departments/`  `[perms: department:view]`
- `POST /api/v1/departments/`  `[perms: department:add]`
- `DELETE /api/v1/departments/{obj_id}`  `[perms: department:delete]`
- `GET /api/v1/departments/{obj_id}`  `[perms: department:view]`
- `PATCH /api/v1/departments/{obj_id}`  `[perms: department:edit]`

### `/api/v1/divisions` (5 routes)

- `GET /api/v1/divisions/`  `[perms: division:view]`
- `POST /api/v1/divisions/`  `[perms: division:add]`
- `DELETE /api/v1/divisions/{obj_id}`  `[perms: division:delete]`
- `GET /api/v1/divisions/{obj_id}`  `[perms: division:view]`
- `PATCH /api/v1/divisions/{obj_id}`  `[perms: division:edit]`

### `/api/v1/dtr-adjustments` (5 routes)

- `GET /api/v1/dtr-adjustments/`  `[perms: daily_time_record:view]`
- `POST /api/v1/dtr-adjustments/`  `[perms: daily_time_record:add]`
- `GET /api/v1/dtr-adjustments/{obj_id}`  `[perms: daily_time_record:view]`
- `POST /api/v1/dtr-adjustments/{obj_id}/approve`  `[perms: daily_time_record:edit]`
- `POST /api/v1/dtr-adjustments/{obj_id}/reject`  `[perms: daily_time_record:edit]`

### `/api/v1/emp-tasks` (7 routes)

- `GET /api/v1/emp-tasks/`  `[perms: emp_task:view]`
- `POST /api/v1/emp-tasks/`  `[perms: emp_task:add]`
- `DELETE /api/v1/emp-tasks/{obj_id}`  `[perms: emp_task:delete]`
- `GET /api/v1/emp-tasks/{obj_id}`  `[perms: emp_task:view]`
- `PATCH /api/v1/emp-tasks/{obj_id}`  `[perms: emp_task:edit]`
- `POST /api/v1/emp-tasks/{obj_id}/approve`  `[perms: emp_project:edit]`
- `POST /api/v1/emp-tasks/{obj_id}/deny`  `[perms: emp_project:edit]`

### `/api/v1/employee-projects` (6 routes)

- `GET /api/v1/employee-projects/`  `[perms: emp_project:view]`
- `POST /api/v1/employee-projects/`  `[perms: emp_project:add]`
- `DELETE /api/v1/employee-projects/{obj_id}`  `[perms: emp_project:delete]`
- `GET /api/v1/employee-projects/{obj_id}`  `[perms: emp_project:view]`
- `PATCH /api/v1/employee-projects/{obj_id}`  `[perms: emp_project:edit]`
- `POST /api/v1/employee-projects/{obj_id}/unassign`  `[perms: emp_project:edit]`

### `/api/v1/employees` (16 routes)

- `GET /api/v1/employees/`  `[perms: emp_list:view]`
- `POST /api/v1/employees/`  `[perms: emp_list:add]`
- `GET /api/v1/employees/me`  `[perms: emp_list:view]`
- `GET /api/v1/employees/{employee_id}/additional-records`
- `PATCH /api/v1/employees/{employee_id}/additional-records`
- `GET /api/v1/employees/{employee_id}/attachments`
- `POST /api/v1/employees/{employee_id}/attachments`
- `DELETE /api/v1/employees/{employee_id}/attachments/{attachment_id}`
- `GET /api/v1/employees/{employee_id}/leave-calendar`  `[perms: emp_leaves:view]`
- `GET /api/v1/employees/{employee_id}/leave-enrollments`  `[perms: emp_leaves:view]`
- `POST /api/v1/employees/{employee_id}/leave-enrollments`  `[perms: emp_leaves:add]`
- `GET /api/v1/employees/{employee_id}/leave-ledger`  `[perms: emp_leaves:view]`
- `GET /api/v1/employees/{employee_id}/leave-ledger/events`  `[perms: emp_leaves:view]`
- `DELETE /api/v1/employees/{obj_id}`  `[perms: emp_list:delete]`
- `GET /api/v1/employees/{obj_id}`  `[perms: emp_list:view]`
- `PATCH /api/v1/employees/{obj_id}`  `[perms: emp_list:edit]`

### `/api/v1/holidays` (5 routes)

- `GET /api/v1/holidays/`  `[perms: holiday_config:view]`
- `POST /api/v1/holidays/`  `[perms: holiday_config:add]`
- `GET /api/v1/holidays/instances`  `[perms: holiday_config:view]`
- `POST /api/v1/holidays/instances`  `[perms: holiday_config:add]`
- `PATCH /api/v1/holidays/{config_id}`  `[perms: holiday_config:edit]`

### `/api/v1/items` (5 routes)

- `GET /api/v1/items/`
- `POST /api/v1/items/`
- `DELETE /api/v1/items/{id}`
- `GET /api/v1/items/{id}`
- `PUT /api/v1/items/{id}`

### `/api/v1/leave` (3 routes)

- `POST /api/v1/leave/admin/accrue`  `[perms: leave_policy:admin]`
- `POST /api/v1/leave/admin/adjust`  `[perms: leave_policy:admin]`
- `POST /api/v1/leave/admin/carryover`  `[perms: leave_policy:admin]`

### `/api/v1/leave-policies` (5 routes)

- `GET /api/v1/leave-policies/`  `[perms: leave_policy:view]`
- `POST /api/v1/leave-policies/`  `[perms: leave_policy:add]`
- `DELETE /api/v1/leave-policies/{policy_id}`  `[perms: leave_policy:delete]`
- `GET /api/v1/leave-policies/{policy_id}`  `[perms: leave_policy:view]`
- `PATCH /api/v1/leave-policies/{policy_id}`  `[perms: leave_policy:edit]`

### `/api/v1/leave-requests` (6 routes)

- `GET /api/v1/leave-requests/`  `[perms: leave_request:view]`
- `POST /api/v1/leave-requests/`  `[perms: leave_request:add]`
- `GET /api/v1/leave-requests/{request_id}`  `[perms: leave_request:view]`
- `POST /api/v1/leave-requests/{request_id}/approve`  `[perms: leave_request:approve]`
- `POST /api/v1/leave-requests/{request_id}/cancel`  `[perms: leave_request:approve]`
- `POST /api/v1/leave-requests/{request_id}/reject`  `[perms: leave_request:approve]`

### `/api/v1/login` (3 routes)

- `POST /api/v1/login/access-token`
- `POST /api/v1/login/refresh-token`
- `POST /api/v1/login/test-token`

### `/api/v1/logout` (1 routes)

- `POST /api/v1/logout`

### `/api/v1/lots` (5 routes)

- `GET /api/v1/lots/`  `[perms: projects:view]`
- `POST /api/v1/lots/`  `[perms: projects:add]`
- `DELETE /api/v1/lots/{obj_id}`  `[perms: projects:delete]`
- `GET /api/v1/lots/{obj_id}`  `[perms: projects:view]`
- `PATCH /api/v1/lots/{obj_id}`  `[perms: projects:edit]`

### `/api/v1/model-types` (5 routes)

- `GET /api/v1/model-types/`  `[perms: model_types:view]`
- `POST /api/v1/model-types/`  `[perms: model_types:add]`
- `DELETE /api/v1/model-types/{obj_id}`  `[perms: model_types:delete]`
- `GET /api/v1/model-types/{obj_id}`  `[perms: model_types:view]`
- `PATCH /api/v1/model-types/{obj_id}`  `[perms: model_types:edit]`

### `/api/v1/models` (5 routes)

- `GET /api/v1/models/`  `[perms: models:view]`
- `POST /api/v1/models/`  `[perms: models:add]`
- `DELETE /api/v1/models/{obj_id}`  `[perms: models:delete]`
- `GET /api/v1/models/{obj_id}`  `[perms: models:view]`
- `PATCH /api/v1/models/{obj_id}`  `[perms: models:edit]`

### `/api/v1/notifications` (7 routes)

- `GET /api/v1/notifications/`  `[perms: notification:view]`
- `POST /api/v1/notifications/`  `[perms: notification:add]`
- `POST /api/v1/notifications/mark-all-read`  `[perms: notification:edit]`
- `POST /api/v1/notifications/pre-payday-check`  `[perms: notification:add]`
- `GET /api/v1/notifications/unread-count`  `[perms: notification:view]`
- `GET /api/v1/notifications/{notification_id}`  `[perms: notification:view]`
- `POST /api/v1/notifications/{notification_id}/read`  `[perms: notification:edit]`

### `/api/v1/openapi.json` (1 routes)

- `GET /api/v1/openapi.json`

### `/api/v1/owners` (6 routes)

- `GET /api/v1/owners/`  `[perms: owner:view]`
- `POST /api/v1/owners/`  `[perms: owner:add]`
- `DELETE /api/v1/owners/{obj_id}`  `[perms: owner:delete]`
- `GET /api/v1/owners/{obj_id}`  `[perms: owner:view]`
- `PATCH /api/v1/owners/{obj_id}`  `[perms: owner:edit]`
- `GET /api/v1/owners/{obj_id}/lot`  `[perms: owner:view]`

### `/api/v1/password-recovery` (1 routes)

- `POST /api/v1/password-recovery/{email}`

### `/api/v1/password-recovery-html-content` (1 routes)

- `POST /api/v1/password-recovery-html-content/{email}`

### `/api/v1/payroll` (45 routes)

- `POST /api/v1/payroll/amortizations/{amortization_id}/pay`  `[perms: payroll:edit]`
- `GET /api/v1/payroll/bir-brackets/`  `[perms: payroll:view]`
- `POST /api/v1/payroll/bir-brackets/`  `[perms: payroll:add]`
- `POST /api/v1/payroll/bir/calculate`
- `POST /api/v1/payroll/calculate-contributions/`
- `GET /api/v1/payroll/employees/{employee_id}/loans`  `[perms: payroll:view]`
- `GET /api/v1/payroll/employees/{employee_id}/payslip`  `[perms: payroll:view]`
- `GET /api/v1/payroll/employees/{employee_id}/salary`  `[perms: payroll:view]`
- `POST /api/v1/payroll/employees/{employee_id}/salary`  `[perms: payroll:add]`
- `GET /api/v1/payroll/integrations`  `[perms: payroll:view]`
- `POST /api/v1/payroll/integrations`  `[perms: payroll:add]`
- `DELETE /api/v1/payroll/integrations/mappings/{mapping_id}`  `[perms: payroll:delete]`
- `PATCH /api/v1/payroll/integrations/mappings/{mapping_id}`  `[perms: payroll:edit]`
- `DELETE /api/v1/payroll/integrations/{config_id}`  `[perms: payroll:delete]`
- `GET /api/v1/payroll/integrations/{config_id}`  `[perms: payroll:view]`
- `PATCH /api/v1/payroll/integrations/{config_id}`  `[perms: payroll:edit]`
- `GET /api/v1/payroll/integrations/{config_id}/mappings`  `[perms: payroll:view]`
- `POST /api/v1/payroll/integrations/{config_id}/mappings`  `[perms: payroll:add]`
- `POST /api/v1/payroll/loans/`  `[perms: payroll:add]`
- `DELETE /api/v1/payroll/loans/{loan_id}`  `[perms: payroll:delete]`
- `GET /api/v1/payroll/loans/{loan_id}`  `[perms: payroll:view]`
- `GET /api/v1/payroll/loans/{loan_id}/amortizations`  `[perms: payroll:view]`
- `POST /api/v1/payroll/loans/{loan_id}/amortizations`  `[perms: payroll:add]`
- `GET /api/v1/payroll/pagibig-brackets/`  `[perms: payroll:view]`
- `POST /api/v1/payroll/pagibig-brackets/`  `[perms: payroll:add]`
- `POST /api/v1/payroll/pagibig/calculate`
- `GET /api/v1/payroll/philhealth-brackets/`  `[perms: payroll:view]`
- `POST /api/v1/payroll/philhealth-brackets/`  `[perms: payroll:add]`
- `POST /api/v1/payroll/philhealth/calculate`
- `GET /api/v1/payroll/runs`  `[perms: payroll:view]`
- `POST /api/v1/payroll/runs/generate`
- `POST /api/v1/payroll/runs/preview`  `[perms: payroll:view]`
- `GET /api/v1/payroll/runs/status`  `[perms: payroll:view]`
- `GET /api/v1/payroll/runs/{run_id}`  `[perms: payroll:view]`
- `POST /api/v1/payroll/runs/{run_id}/approve`  `[perms: payroll:edit]`
- `GET /api/v1/payroll/runs/{run_id}/payslips`  `[perms: payroll:view]`
- `POST /api/v1/payroll/runs/{run_id}/void`  `[perms: payroll:edit]`
- `GET /api/v1/payroll/salaries/{salary_id}`  `[perms: payroll:view]`
- `PATCH /api/v1/payroll/salaries/{salary_id}`  `[perms: payroll:edit]`
- `GET /api/v1/payroll/sss-brackets/`  `[perms: payroll:view]`
- `POST /api/v1/payroll/sss-brackets/`  `[perms: payroll:add]`
- `DELETE /api/v1/payroll/sss-brackets/{bracket_id}`  `[perms: payroll:delete]`
- `GET /api/v1/payroll/sss-brackets/{bracket_id}`  `[perms: payroll:view]`
- `PATCH /api/v1/payroll/sss-brackets/{bracket_id}`  `[perms: payroll:edit]`
- `POST /api/v1/payroll/sss/calculate`

### `/api/v1/phases` (5 routes)

- `GET /api/v1/phases/`  `[perms: phase:view]`
- `POST /api/v1/phases/`  `[perms: phase:add]`
- `DELETE /api/v1/phases/{obj_id}`  `[perms: phase:delete]`
- `GET /api/v1/phases/{obj_id}`  `[perms: phase:view]`
- `PATCH /api/v1/phases/{obj_id}`  `[perms: phase:edit]`

### `/api/v1/positions` (5 routes)

- `GET /api/v1/positions/`  `[perms: emp_settings:view]`
- `POST /api/v1/positions/`  `[perms: emp_settings:add]`
- `DELETE /api/v1/positions/{obj_id}`  `[perms: emp_settings:delete]`
- `GET /api/v1/positions/{obj_id}`  `[perms: emp_settings:view]`
- `PATCH /api/v1/positions/{obj_id}`  `[perms: emp_settings:edit]`

### `/api/v1/private` (1 routes)

- `POST /api/v1/private/users/`

### `/api/v1/project-types` (5 routes)

- `GET /api/v1/project-types/`  `[perms: project_type:view]`
- `POST /api/v1/project-types/`  `[perms: project_type:add]`
- `DELETE /api/v1/project-types/{obj_id}`  `[perms: project_type:delete]`
- `GET /api/v1/project-types/{obj_id}`  `[perms: project_type:view]`
- `PATCH /api/v1/project-types/{obj_id}`  `[perms: project_type:edit]`

### `/api/v1/projects` (5 routes)

- `GET /api/v1/projects/`  `[perms: projects:view]`
- `POST /api/v1/projects/`  `[perms: projects:add]`
- `DELETE /api/v1/projects/{obj_id}`  `[perms: projects:delete]`
- `GET /api/v1/projects/{obj_id}`  `[perms: projects:view]`
- `PATCH /api/v1/projects/{obj_id}`  `[perms: projects:edit]`

### `/api/v1/rbac` (7 routes)

- `GET /api/v1/rbac/me/permissions`
- `GET /api/v1/rbac/modules`  `[perms: administration:view]`
- `GET /api/v1/rbac/roles`  `[perms: administration:view]`
- `POST /api/v1/rbac/roles`  `[perms: administration:add]`
- `DELETE /api/v1/rbac/roles/{role_id}`  `[perms: administration:delete]`
- `PATCH /api/v1/rbac/roles/{role_id}`  `[perms: administration:edit]`
- `GET /api/v1/rbac/roles/{role_id}/permissions`  `[perms: administration:view]`

### `/api/v1/reports` (5 routes)

- `GET /api/v1/reports/attendance-summary`  `[perms: report:view]`
- `GET /api/v1/reports/headcount`  `[perms: report:view]`
- `GET /api/v1/reports/leave-balance`  `[perms: report:view]`
- `GET /api/v1/reports/payroll-register`  `[perms: report:view]`
- `GET /api/v1/reports/payroll/summary`  `[perms: report:view]`

### `/api/v1/reset-password` (1 routes)

- `POST /api/v1/reset-password/`

### `/api/v1/shifts` (5 routes)

- `GET /api/v1/shifts/`  `[perms: shifts:view]`
- `POST /api/v1/shifts/`  `[perms: shifts:add]`
- `DELETE /api/v1/shifts/{obj_id}`  `[perms: shifts:delete]`
- `GET /api/v1/shifts/{obj_id}`  `[perms: shifts:view]`
- `PATCH /api/v1/shifts/{obj_id}`  `[perms: shifts:edit]`

### `/api/v1/subdivisions` (5 routes)

- `GET /api/v1/subdivisions/`  `[perms: subdivision:view]`
- `POST /api/v1/subdivisions/`  `[perms: subdivision:add]`
- `DELETE /api/v1/subdivisions/{obj_id}`  `[perms: subdivision:delete]`
- `GET /api/v1/subdivisions/{obj_id}`  `[perms: subdivision:view]`
- `PATCH /api/v1/subdivisions/{obj_id}`  `[perms: subdivision:edit]`

### `/api/v1/users` (11 routes)

- `GET /api/v1/users/`
- `POST /api/v1/users/`
- `DELETE /api/v1/users/me`
- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me`
- `PATCH /api/v1/users/me/password`
- `POST /api/v1/users/signup`  `[perms: administration:add]`
- `DELETE /api/v1/users/{user_id}`
- `GET /api/v1/users/{user_id}`
- `PATCH /api/v1/users/{user_id}`
- `POST /api/v1/users/{user_id}/role`  `[perms: administration:edit]`

### `/api/v1/utils` (2 routes)

- `GET /api/v1/utils/health-check/`
- `POST /api/v1/utils/test-email/`

## Backend domain packages (`backend/app/`): 12 domains

Layer files present per package. `backend/app/common/` holds shared infra and
is omitted here, as are `config` (engine/settings) and `email-templates`.

- `attendance`: models.py, schemas.py, routes.py, services.py, selectors.py
- `audit`: models.py, routes.py
- `auth`: models.py, schemas.py, services.py, selectors.py
- `dashboard`: schemas.py, routes.py, services.py
- `employee`: models.py, schemas.py, routes.py, services.py, selectors.py
- `item`: models.py, schemas.py, routes/, services.py, selectors.py
- `leave`: models.py, schemas.py, routes.py, services.py, selectors.py
- `notification`: models.py, schemas.py, routes.py, services.py
- `payroll`: models.py, schemas.py, routes.py, services.py, selectors.py
- `rbac`: models.py, schemas.py, routes.py, services.py, selectors.py
- `reports`: routes.py
- `user`: models.py, schemas.py, routes/, services.py, selectors.py

## Frontend features (`frontendv3/src/features/`): 32 features

API columns are modules imported from `@/lib/api/*` (grep-based, per-verified
reliable in the source tree's single-line import style) with plumbing
(`client`/`types`) excluded. Flags: `route` = matching dir under
`src/routes/_authenticated/`, `form` = a `*form.tsx` component exists,
`test` = a colocated Vitest file exists.

- `apps`: api `none`; flags: route
- `attendance`: api `none`; flags: test
- `auth`: api `auth`; flags: form, test
- `blocks`: api `blocks`, `phases`; flags: route, form, test
- `categories`: api `categories`; flags: route, form
- `chats`: api `none`; flags: route
- `daily-time-records`: api `daily-time-records`; flags: route, test
- `dashboard`: api `none`; flags: test
- `departments`: api `departments`, `divisions`; flags: route, form, test
- `divisions`: api `divisions`; flags: route, form, test
- `dtr-adjustments`: api `dtr-adjustments`; flags: route, form, test
- `emp-tasks`: api `emp-tasks`, `employee-projects`; flags: route, form
- `employee-projects`: api `employee-projects`, `employees`, `projects`; flags: route, form, test
- `employees`: api `employees`; flags: route, test
- `holidays`: api `holidays`; flags: route, form, test
- `leave-calendar`: api `leave-ledger`; flags: route, test
- `leave-ledger`: api `leave-ledger`; flags: route, test
- `leave-requests`: api `leave-requests`; flags: route, form, test
- `lots`: api `blocks`, `lots`; flags: route, form, test
- `model-types`: api `model-types`; flags: route, form
- `models`: api `model-types`, `models`; flags: route, form
- `owners`: api `owners`; flags: route, form, test
- `phases`: api `phases`, `subdivisions`; flags: route, form, test
- `positions`: api `departments`, `positions`; flags: route, form
- `project-types`: api `project-types`; flags: route, form
- `projects`: api `project-types`, `projects`, `subdivisions`; flags: route, form
- `roles`: api `roles`; flags: route, form, test
- `settings`: api `none`; flags: route, form
- `shifts`: api `shifts`; flags: route, form
- `subdivisions`: api `blocks`, `categories`, `lots`, `phases`, `projects`, `subdivisions`; flags: route, form, test
- `tasks`: api `none`; flags: route, test
- `users`: api `none`; flags: route, test

## Migration chain (oldest -> newest): 23 revisions, single head `3f0e3e733925`

Parsed statically from `backend/alembic/versions/*.py` (`revision` /
`down_revision` tokens); no `alembic history` subprocess required.

1. `e2412789c190` - Initialize models
2. `9c0a54914c78` - Add max length for string(varchar) fields in User and Items models
3. `d98dd8ec85a3` - Edit replace id integers in all models to use UUID instead
4. `1a31ce608336` - Add cascade delete relationships
5. `fe56fa70289e` - Add created_at to User and Item
6. `0f1703dcd862` - add refresh_token table for revocable sessions
7. `10fc690ffb09` - add rbac module role role_permission and user.role_id
8. `7286295e0903` - add employee core and org structure tables
9. `b1fd80d00cf0` - add unique index on category lot_id
10. `1c721a424eb4` - add shift and daily_time_record tables (Phase 2A)
11. `c3b726b97e47` - add dtr_adjustment table (Phase 2B)
12. `c085a769992a` - add can_approve and can_admin columns to role_permission (Phase b3)
13. `b9748b3e7b5c` - add leave_policy, enrollment, request, ledger, holiday tables (Phase b3)
14. `d4b4a4d0b4a1` - add payroll bracket, integration, salary, run, entry, loan tables (Phase B4A)
15. `d5b5b4e1b4a2` - add missing payroll table indexes (standalone FK indexes)
16. `f176e167c8e7` - change employee_salary unique constraint to include effective_date
17. `3009113137ba` - add notification and audit_log tables
18. `bc349a74ea22` - add notification and audit_log tables
19. `9c7a54c3b67f` - add is_deleted to audit_log
20. `cc9df25cd8ed` - add is_readonly to payroll_run and payroll_entry (Phase B6)
21. `a1b2c3d4e5f6` - add pre_payday_check to notificationtype enum
22. `54ff6e36652b` - add_payroll_tables
23. `3f0e3e733925` - change employee_salary unique constraint to include effective_date

## Cross-reference: backend domain <-> frontend feature (exact name match)

The cheapest signal for which frontend screens talk to which backend module.
Name-only match: the frontend feature and the app/ package with the same
basename. Does not replace reading the actual imports for a given feature.

- `attendance` <-> `attendance`
- `auth` <-> `auth`
- `dashboard` <-> `dashboard`

Backend domains with no same-named frontend feature: `audit`, `employee`, `item`, `leave`, `notification`, `payroll`, `rbac`, `reports`, `user`
(A name mismatch here does not mean the domain is unused: `app/employee/` serves
routers for ~16 resources that each have their own frontend feature, and
`attendance`/`leave`/`rbac` back multiple differently-named feature screens.)

Frontend features with no same-named backend domain: `apps`, `blocks`, `categories`, `chats`, `daily-time-records`, `departments`, `divisions`, `dtr-adjustments`, `emp-tasks`, `employee-projects`, `employees`, `holidays`, `leave-calendar`, `leave-ledger`, `leave-requests`, `lots`, `model-types`, `models`, `owners`, `phases`, `positions`, `project-types`, `projects`, `roles`, `settings`, `shifts`, `subdivisions`, `tasks`, `users`
(Many map to a differently-named backend domain, e.g. all `leave-*`/`holidays`
features hit `app/leave/`, and the CRUD screens under `app/employee/`;
`apps`/`chats`/`tasks`/`settings`/`users` are unwired template-demo features.)
