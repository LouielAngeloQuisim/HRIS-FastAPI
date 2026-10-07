# Architecture Map (generated, do not hand-edit)
Generated: 2026-10-08
Source commit: 8f01a09f42cc712486e0ba6d813f3a9ce06af802
Provenance: the content below was extracted from the working tree at the
Source commit shown. When this file is itself committed, the commit that
stores it is a DESCENDANT of the Source commit, not the Source commit.
Regenerate this file with `bash scripts/gen-map.sh [SOURCE_COMMIT]`
rather than editing it by hand.

## Backend routes (`/api/*`): 284 endpoints in 40 groups

Grouped by top-level prefix. Format: `METHOD path  [perms: module:action]`.
No `[perms]` tag means the route has no `require_permission` dependency:
either auth/public endpoints, template demo resources (items, login flow),
or routes protected by the route_policy whitelist instead of RBAC modules.

### `/api/v1/audit-log` (2 routes)

- `GET /api/v1/audit-log/`  `[perms: audit:view]`
- `GET /api/v1/audit-log/{log_id}`  `[perms: audit:view]`

### `/api/v1/blocks` (6 routes)

- `GET /api/v1/blocks/`  `[perms: projects:view]`
- `POST /api/v1/blocks/`  `[perms: projects:add]`
- `GET /api/v1/blocks/labels`  `[perms: projects:view]`
- `DELETE /api/v1/blocks/{obj_id}`  `[perms: projects:delete]`
- `GET /api/v1/blocks/{obj_id}`  `[perms: projects:view]`
- `PATCH /api/v1/blocks/{obj_id}`  `[perms: projects:edit]`

### `/api/v1/categories` (6 routes)

- `GET /api/v1/categories/`  `[perms: category:view]`
- `POST /api/v1/categories/`  `[perms: category:add]`
- `GET /api/v1/categories/labels`  `[perms: category:view]`
- `DELETE /api/v1/categories/{obj_id}`  `[perms: category:delete]`
- `GET /api/v1/categories/{obj_id}`  `[perms: category:view]`
- `PATCH /api/v1/categories/{obj_id}`  `[perms: category:edit]`

### `/api/v1/daily-time-records` (14 routes)

- `GET /api/v1/daily-time-records/`  `[perms: daily_time_record:view]`
- `POST /api/v1/daily-time-records/`  `[perms: daily_time_record:add]`
- `POST /api/v1/daily-time-records/import-batches/commit`  `[perms: daily_time_record:add]`
- `POST /api/v1/daily-time-records/import-batches/preflight`  `[perms: daily_time_record:add]`
- `GET /api/v1/daily-time-records/import-batches/{batch_id}`  `[perms: daily_time_record:view]`
- `POST /api/v1/daily-time-records/reconcile-imports`  `[perms: daily_time_record:add]`
- `DELETE /api/v1/daily-time-records/{obj_id}`  `[perms: daily_time_record:delete]`
- `GET /api/v1/daily-time-records/{obj_id}`  `[perms: daily_time_record:view]`
- `PATCH /api/v1/daily-time-records/{obj_id}`  `[perms: daily_time_record:edit]`
- `POST /api/v1/daily-time-records/{obj_id}/approve-overtime`  `[perms: daily_time_record:edit]`
- `GET /api/v1/daily-time-records/{obj_id}/intervals`  `[perms: daily_time_record:view]`
- `PUT /api/v1/daily-time-records/{obj_id}/intervals`  `[perms: daily_time_record:edit]`
- `GET /api/v1/daily-time-records/{obj_id}/overtime-decisions`  `[perms: daily_time_record:view]`
- `POST /api/v1/daily-time-records/{obj_id}/reject-overtime`  `[perms: daily_time_record:edit]`

### `/api/v1/dashboard` (1 routes)

- `GET /api/v1/dashboard/`  `[perms: emp_list:view]`

### `/api/v1/departments` (6 routes)

- `GET /api/v1/departments/`  `[perms: department:view]`
- `POST /api/v1/departments/`  `[perms: department:add]`
- `GET /api/v1/departments/labels`  `[perms: department:view]`
- `DELETE /api/v1/departments/{obj_id}`  `[perms: department:delete]`
- `GET /api/v1/departments/{obj_id}`  `[perms: department:view]`
- `PATCH /api/v1/departments/{obj_id}`  `[perms: department:edit]`

### `/api/v1/divisions` (6 routes)

- `GET /api/v1/divisions/`  `[perms: division:view]`
- `POST /api/v1/divisions/`  `[perms: division:add]`
- `GET /api/v1/divisions/labels`  `[perms: division:view]`
- `DELETE /api/v1/divisions/{obj_id}`  `[perms: division:delete]`
- `GET /api/v1/divisions/{obj_id}`  `[perms: division:view]`
- `PATCH /api/v1/divisions/{obj_id}`  `[perms: division:edit]`

### `/api/v1/dtr-adjustments` (5 routes)

- `GET /api/v1/dtr-adjustments/`  `[perms: daily_time_record:view]`
- `POST /api/v1/dtr-adjustments/`  `[perms: daily_time_record:add]`
- `GET /api/v1/dtr-adjustments/{obj_id}`  `[perms: daily_time_record:view]`
- `POST /api/v1/dtr-adjustments/{obj_id}/approve`  `[perms: daily_time_record:edit]`
- `POST /api/v1/dtr-adjustments/{obj_id}/reject`  `[perms: daily_time_record:edit]`

### `/api/v1/emp-tasks` (8 routes)

- `GET /api/v1/emp-tasks/`  `[perms: emp_task:view]`
- `POST /api/v1/emp-tasks/`  `[perms: emp_task:add]`
- `GET /api/v1/emp-tasks/labels`  `[perms: emp_task:view]`
- `DELETE /api/v1/emp-tasks/{obj_id}`  `[perms: emp_task:delete]`
- `GET /api/v1/emp-tasks/{obj_id}`  `[perms: emp_task:view]`
- `PATCH /api/v1/emp-tasks/{obj_id}`  `[perms: emp_task:edit]`
- `POST /api/v1/emp-tasks/{obj_id}/approve`  `[perms: emp_project:edit]`
- `POST /api/v1/emp-tasks/{obj_id}/deny`  `[perms: emp_project:edit]`

### `/api/v1/employee-projects` (7 routes)

- `GET /api/v1/employee-projects/`  `[perms: emp_project:view]`
- `POST /api/v1/employee-projects/`  `[perms: emp_project:add]`
- `GET /api/v1/employee-projects/labels`  `[perms: emp_project:view]`
- `DELETE /api/v1/employee-projects/{obj_id}`  `[perms: emp_project:delete]`
- `GET /api/v1/employee-projects/{obj_id}`  `[perms: emp_project:view]`
- `PATCH /api/v1/employee-projects/{obj_id}`  `[perms: emp_project:edit]`
- `POST /api/v1/employee-projects/{obj_id}/unassign`  `[perms: emp_project:edit]`

### `/api/v1/employee-shift-assignments` (3 routes)

- `GET /api/v1/employee-shift-assignments/`  `[perms: shifts:view]`
- `POST /api/v1/employee-shift-assignments/`  `[perms: shifts:add]`
- `PATCH /api/v1/employee-shift-assignments/{assignment_id}`  `[perms: shifts:edit]`

### `/api/v1/employees` (17 routes)

- `GET /api/v1/employees/`  `[perms: emp_list:view]`
- `POST /api/v1/employees/`  `[perms: emp_list:add]`
- `GET /api/v1/employees/labels`  `[perms: emp_list:view]`
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

### `/api/v1/holidays` (6 routes)

- `GET /api/v1/holidays/`  `[perms: holiday_config:view]`
- `POST /api/v1/holidays/`  `[perms: holiday_config:add]`
- `GET /api/v1/holidays/instances`  `[perms: holiday_config:view]`
- `POST /api/v1/holidays/instances`  `[perms: holiday_config:add]`
- `DELETE /api/v1/holidays/{config_id}`  `[perms: holiday_config:delete]`
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

### `/api/v1/lots` (6 routes)

- `GET /api/v1/lots/`  `[perms: projects:view]`
- `POST /api/v1/lots/`  `[perms: projects:add]`
- `GET /api/v1/lots/labels`  `[perms: projects:view]`
- `DELETE /api/v1/lots/{obj_id}`  `[perms: projects:delete]`
- `GET /api/v1/lots/{obj_id}`  `[perms: projects:view]`
- `PATCH /api/v1/lots/{obj_id}`  `[perms: projects:edit]`

### `/api/v1/model-types` (6 routes)

- `GET /api/v1/model-types/`  `[perms: model_types:view]`
- `POST /api/v1/model-types/`  `[perms: model_types:add]`
- `GET /api/v1/model-types/labels`  `[perms: model_types:view]`
- `DELETE /api/v1/model-types/{obj_id}`  `[perms: model_types:delete]`
- `GET /api/v1/model-types/{obj_id}`  `[perms: model_types:view]`
- `PATCH /api/v1/model-types/{obj_id}`  `[perms: model_types:edit]`

### `/api/v1/models` (6 routes)

- `GET /api/v1/models/`  `[perms: models:view]`
- `POST /api/v1/models/`  `[perms: models:add]`
- `GET /api/v1/models/labels`  `[perms: models:view]`
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

### `/api/v1/owners` (7 routes)

- `GET /api/v1/owners/`  `[perms: owner:view]`
- `POST /api/v1/owners/`  `[perms: owner:add]`
- `GET /api/v1/owners/labels`  `[perms: owner:view]`
- `DELETE /api/v1/owners/{obj_id}`  `[perms: owner:delete]`
- `GET /api/v1/owners/{obj_id}`  `[perms: owner:view]`
- `PATCH /api/v1/owners/{obj_id}`  `[perms: owner:edit]`
- `GET /api/v1/owners/{obj_id}/lot`  `[perms: owner:view]`

### `/api/v1/password-recovery` (1 routes)

- `POST /api/v1/password-recovery/{email}`

### `/api/v1/password-recovery-html-content` (1 routes)

- `POST /api/v1/password-recovery-html-content/{email}`

### `/api/v1/payroll` (77 routes)

- `POST /api/v1/payroll/amortizations/{amortization_id}/pay`  `[perms: payroll:edit]`
- `GET /api/v1/payroll/bir-brackets/`  `[perms: payroll:view]`
- `POST /api/v1/payroll/bir-brackets/`  `[perms: payroll:add]`
- `DELETE /api/v1/payroll/bir-brackets/{bracket_id}`  `[perms: payroll:delete]`
- `PATCH /api/v1/payroll/bir-brackets/{bracket_id}`  `[perms: payroll:edit]`
- `POST /api/v1/payroll/bir/calculate`
- `POST /api/v1/payroll/calculate-contributions/`
- `GET /api/v1/payroll/employees/{employee_id}/loans`  `[perms: payroll:view]`
- `GET /api/v1/payroll/employees/{employee_id}/payslip`  `[perms: payroll:view]`
- `GET /api/v1/payroll/employees/{employee_id}/salary`  `[perms: payroll:view]`
- `POST /api/v1/payroll/employees/{employee_id}/salary`  `[perms: payroll:add]`
- `GET /api/v1/payroll/employees/{employee_id}/tax-year-declarations/{tax_year}`  `[perms: payroll:view]`
- `PUT /api/v1/payroll/employees/{employee_id}/tax-year-declarations/{tax_year}`  `[perms: payroll:approve]`
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
- `DELETE /api/v1/payroll/pagibig-brackets/{bracket_id}`  `[perms: payroll:delete]`
- `PATCH /api/v1/payroll/pagibig-brackets/{bracket_id}`  `[perms: payroll:edit]`
- `POST /api/v1/payroll/pagibig/calculate`
- `GET /api/v1/payroll/pay-group-assignments`  `[perms: payroll:view]`
- `POST /api/v1/payroll/pay-group-assignments`  `[perms: payroll:add]`
- `PATCH /api/v1/payroll/pay-group-assignments/{assignment_id}`  `[perms: payroll:edit]`
- `GET /api/v1/payroll/pay-groups`  `[perms: payroll:view]`
- `POST /api/v1/payroll/pay-groups`  `[perms: payroll:add]`
- `GET /api/v1/payroll/pay-groups/{group_id}/periods`  `[perms: payroll:view]`
- `GET /api/v1/payroll/philhealth-brackets/`  `[perms: payroll:view]`
- `POST /api/v1/payroll/philhealth-brackets/`  `[perms: payroll:add]`
- `DELETE /api/v1/payroll/philhealth-brackets/{bracket_id}`  `[perms: payroll:delete]`
- `PATCH /api/v1/payroll/philhealth-brackets/{bracket_id}`  `[perms: payroll:edit]`
- `POST /api/v1/payroll/philhealth/calculate`
- `GET /api/v1/payroll/policies`  `[perms: payroll:view]`
- `POST /api/v1/payroll/policies`  `[perms: payroll:add]`
- `POST /api/v1/payroll/policies/{policy_id}/confirm`  `[perms: payroll:edit]`
- `GET /api/v1/payroll/runs`  `[perms: payroll:view]`
- `GET /api/v1/payroll/runs/attendance-calculation-preview`  `[perms: payroll:view]`
- `POST /api/v1/payroll/runs/generate`  `[perms: payroll:add]`
- `GET /api/v1/payroll/runs/preflight`  `[perms: payroll:view]`
- `POST /api/v1/payroll/runs/prepare-attendance-draft`  `[perms: payroll:add]`
- `POST /api/v1/payroll/runs/preview`  `[perms: payroll:view]`
- `GET /api/v1/payroll/runs/status`  `[perms: payroll:view]`
- `GET /api/v1/payroll/runs/{run_id}`  `[perms: payroll:view]`
- `POST /api/v1/payroll/runs/{run_id}/approve`  `[perms: payroll:edit]`
- `GET /api/v1/payroll/runs/{run_id}/delivery-status`  `[perms: payroll:view]`
- `POST /api/v1/payroll/runs/{run_id}/delivery/{job_id}/address`  `[perms: payroll:edit]`
- `POST /api/v1/payroll/runs/{run_id}/delivery/{job_id}/resend`  `[perms: payroll:edit]`
- `GET /api/v1/payroll/runs/{run_id}/entries/{entry_id}/payslip.pdf`  `[perms: payroll:view]`
- `POST /api/v1/payroll/runs/{run_id}/entries/{entry_id}/review`  `[perms: payroll:edit]`
- `POST /api/v1/payroll/runs/{run_id}/finalize`  `[perms: payroll:approve]`
- `GET /api/v1/payroll/runs/{run_id}/payslips`  `[perms: payroll:view]`
- `POST /api/v1/payroll/runs/{run_id}/rebuild-attendance-draft`  `[perms: payroll:edit]`
- `POST /api/v1/payroll/runs/{run_id}/start-review`  `[perms: payroll:edit]`
- `POST /api/v1/payroll/runs/{run_id}/void`  `[perms: payroll:edit]`
- `POST /api/v1/payroll/salaries/bulk/commit`  `[perms: payroll:add]`
- `POST /api/v1/payroll/salaries/bulk/preflight`  `[perms: payroll:add]`
- `DELETE /api/v1/payroll/salaries/{salary_id}`  `[perms: payroll:delete]`
- `GET /api/v1/payroll/salaries/{salary_id}`  `[perms: payroll:view]`
- `PATCH /api/v1/payroll/salaries/{salary_id}`  `[perms: payroll:edit]`
- `GET /api/v1/payroll/salary-roster`  `[perms: payroll:view]`
- `GET /api/v1/payroll/sss-brackets/`  `[perms: payroll:view]`
- `POST /api/v1/payroll/sss-brackets/`  `[perms: payroll:add]`
- `DELETE /api/v1/payroll/sss-brackets/{bracket_id}`  `[perms: payroll:delete]`
- `GET /api/v1/payroll/sss-brackets/{bracket_id}`  `[perms: payroll:view]`
- `PATCH /api/v1/payroll/sss-brackets/{bracket_id}`  `[perms: payroll:edit]`
- `POST /api/v1/payroll/sss/calculate`

### `/api/v1/phases` (6 routes)

- `GET /api/v1/phases/`  `[perms: phase:view]`
- `POST /api/v1/phases/`  `[perms: phase:add]`
- `GET /api/v1/phases/labels`  `[perms: phase:view]`
- `DELETE /api/v1/phases/{obj_id}`  `[perms: phase:delete]`
- `GET /api/v1/phases/{obj_id}`  `[perms: phase:view]`
- `PATCH /api/v1/phases/{obj_id}`  `[perms: phase:edit]`

### `/api/v1/positions` (6 routes)

- `GET /api/v1/positions/`  `[perms: emp_settings:view]`
- `POST /api/v1/positions/`  `[perms: emp_settings:add]`
- `GET /api/v1/positions/labels`  `[perms: emp_settings:view]`
- `DELETE /api/v1/positions/{obj_id}`  `[perms: emp_settings:delete]`
- `GET /api/v1/positions/{obj_id}`  `[perms: emp_settings:view]`
- `PATCH /api/v1/positions/{obj_id}`  `[perms: emp_settings:edit]`

### `/api/v1/private` (1 routes)

- `POST /api/v1/private/users/`

### `/api/v1/project-types` (6 routes)

- `GET /api/v1/project-types/`  `[perms: project_type:view]`
- `POST /api/v1/project-types/`  `[perms: project_type:add]`
- `GET /api/v1/project-types/labels`  `[perms: project_type:view]`
- `DELETE /api/v1/project-types/{obj_id}`  `[perms: project_type:delete]`
- `GET /api/v1/project-types/{obj_id}`  `[perms: project_type:view]`
- `PATCH /api/v1/project-types/{obj_id}`  `[perms: project_type:edit]`

### `/api/v1/projects` (6 routes)

- `GET /api/v1/projects/`  `[perms: projects:view]`
- `POST /api/v1/projects/`  `[perms: projects:add]`
- `GET /api/v1/projects/labels`  `[perms: projects:view]`
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

### `/api/v1/subdivisions` (6 routes)

- `GET /api/v1/subdivisions/`  `[perms: subdivision:view]`
- `POST /api/v1/subdivisions/`  `[perms: subdivision:add]`
- `GET /api/v1/subdivisions/labels`  `[perms: subdivision:view]`
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

## Frontend features (`frontendv3/src/features/`): 39 features

API columns are modules imported from `@/lib/api/*` (grep-based, per-verified
reliable in the source tree's single-line import style) with plumbing
(`client`/`types`) excluded. Flags: `route` = matching dir under
`src/routes/_authenticated/`, `form` = a `*form.tsx` component exists,
`test` = a colocated Vitest file exists.

- `apps`: api `none`; flags: route
- `attendance`: api `none`; flags: test
- `auth`: api `auth`; flags: form, test
- `blocks`: api `blocks`, `phases`, `save-error`; flags: route, form, test
- `categories`: api `blocks`, `categories`, `lots`, `models`, `owners`, `phases`, `projects`, `relationship-label-text`, `relationship-labels`, `save-error`; flags: route, form, test
- `chats`: api `none`; flags: route
- `daily-time-records`: api `daily-time-records`, `relationship-label-text`, `relationship-labels`, `save-error`; flags: route, form, test
- `dashboard`: api `none`; flags: test
- `departments`: api `departments`, `divisions`; flags: route, form, test
- `divisions`: api `divisions`; flags: route, form, test
- `dtr-adjustments`: api `daily-time-records`, `dtr-adjustments`, `relationship-label-text`, `relationship-labels`, `save-error`; flags: route, form, test
- `emp-tasks`: api `emp-tasks`, `employee-projects`, `relationship-label-text`, `relationship-labels`, `save-error`; flags: route, form, test
- `employee-projects`: api `employee-projects`, `employees`, `projects`, `relationship-label-text`, `relationship-labels`, `save-error`; flags: route, form, test
- `employees`: api `employees`, `payroll`, `save-error`; flags: route, form, test
- `holidays`: api `holidays`; flags: route, form, test
- `leave-calendar`: api `employees`, `leave-ledger`; flags: route, test
- `leave-enrollment`: api `employees`, `leave-policies`, `save-error`; flags: test
- `leave-ledger`: api `employees`, `leave-ledger`, `leave-policies`; flags: route, test
- `leave-policies`: api `leave-policies`, `save-error`; flags: route, form, test
- `leave-requests`: api `employees`, `leave-policies`, `leave-requests`, `save-error`; flags: route, form, test
- `lots`: api `blocks`, `lots`, `save-error`; flags: route, form, test
- `model-types`: api `model-types`; flags: route, form
- `models`: api `model-types`, `models`, `save-error`; flags: route, form, test
- `owners`: api `owners`; flags: route, form, test
- `payroll`: api `departments`, `employees`, `payroll`, `save-error`; flags: route, test
- `payroll-config`: api `auth`, `payroll-config`, `save-error`; flags: route, form, test
- `payroll-runs`: api `payroll`; flags: route, test
- `payroll-settings`: api `employees`, `payroll`; flags: (none)
- `phases`: api `phases`, `save-error`, `subdivisions`; flags: route, form, test
- `positions`: api `departments`, `positions`; flags: route, form, test
- `project-types`: api `project-types`; flags: route, form
- `projects`: api `project-types`, `projects`, `relationship-label-text`, `relationship-labels`, `subdivisions`; flags: route, form, test
- `roles`: api `roles`, `save-error`; flags: route, form, test
- `salary`: api `employees`, `payroll`, `save-error`; flags: form, test
- `settings`: api `none`; flags: route, form
- `shifts`: api `employees`, `shifts`; flags: route, form
- `subdivisions`: api `blocks`, `categories`, `lots`, `phases`, `project-types`, `projects`, `save-error`, `subdivisions`; flags: route, form, test
- `tasks`: api `none`; flags: route, test
- `users`: api `none`; flags: route, test

## Migration chain (oldest -> newest): 41 revisions, single head `c2d3e4f5a6b7`

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
24. `7ab12cd44e91` - add partial unique index for DTR import idempotency (QA-01)
25. `8c12ab55d901` - Add durable payroll generation fingerprint.
26. `1b2c3d4e5f60` - Create effective-dated employee shift assignments.
27. `2c3d4e5f6071` - Add a Manila-calendar work date to attendance records.
28. `3d4e5f607182` - Persist idempotency fingerprints for atomic DTR imports.
29. `4e5f60718293` - Record bounded overtime review decisions on attendance records.
30. `5f60718293a4` - Add effective pay groups and versioned payroll policies.
31. `6a718293a4b5` - Add immutable multi-interval attendance revisions.
32. `7b8293a4b5c6` - Record idempotent identities for atomic, explicit salary batches.
33. `8c93a4b5c6d7` - Enforce one active daily attendance record per employee and work date.
34. `9d04b5c6d7e8` - Add payroll review snapshots and durable payslip-delivery outbox.
35. `67e279f8c3cc` - Add monthly payroll contribution ledger
36. `7c8d9e0f1a2b` - Add compensation-to-MSC mapping fields to SSS schedules.
37. `8d9e0f1a2b3c` - Record source references and seed BIR Annex E when no schedule exists.
38. `9e0f1a2b3c4d` - Seed the published 2025 SSS employer and employee contribution schedule.
39. `a0f1a2b3c4d5` - Seed published PhilHealth and Pag-IBIG mandatory schedules when absent.
40. `b1c2d3e4f5a6` - Store reviewed employee tax classification and opening YTD amounts.
41. `c2d3e4f5a6b7` - Track the date covered by opening tax-year balances.

### Migration anomalies (static findings, report-only)

Derived by `scripts/gen-map.sh` from the migration source text only. These
are NOT defects proven by running anything: each needs human review before
any action. Historical migration files are never modified by the generator.

8 finding(s):

- `3009113137ba` (add notification and audit_log tables): `upgrade()` contains no `op.*` call (effectively a no-op migration; its child may carry the intended work)
- `9e0f1a2b3c4d` (Seed the published 2025 SSS employer and employee contribution schedule.): `upgrade()` contains no `op.*` call (effectively a no-op migration; its child may carry the intended work)
- `a0f1a2b3c4d5` (Seed published PhilHealth and Pag-IBIG mandatory schedules when absent.): `upgrade()` contains no `op.*` call (effectively a no-op migration; its child may carry the intended work)
- `3f0e3e733925` (change employee_salary unique constraint to include effective_date), `f176e167c8e7` (change employee_salary unique constraint to include effective_date): identical normalized `upgrade()` constraint-operation signature
- `54ff6e36652b` (add_payroll_tables): description mentions table creation but `upgrade()` contains no `op.create_table` call
- `7286295e0903` (add employee core and org structure tables): creates native enum type(s) `employeestatus` in `upgrade()` with no matching `DROP TYPE` in its `downgrade()` (downgrade leaves the postgres type orphaned; enum cleanup would need a follow-up migration or explicit ops runbook)
- `b9748b3e7b5c` (add leave_policy, enrollment, request, ledger, holiday tables (Phase b3)): creates native enum type(s) `genderscope`, `holidaytype`, `leavecadence`, `leaveledgersource`, `leaverequesteventtype`, `leavestatus`, `maritalstatusscope`, `observeweekendas` in `upgrade()` with no matching `DROP TYPE` in its `downgrade()` (downgrade leaves the postgres type orphaned; enum cleanup would need a follow-up migration or explicit ops runbook)
- `d4b4a4d0b4a1` (add payroll bracket, integration, salary, run, entry, loan tables (Phase B4A)): creates native enum type(s) `connectortype`, `cutofftype`, `loantype`, `payrolladjustmenttype`, `payrollrunstatus`, `paytype` in `upgrade()` with no matching `DROP TYPE` in its `downgrade()` (downgrade leaves the postgres type orphaned; enum cleanup would need a follow-up migration or explicit ops runbook)

## Cross-reference: backend domain <-> frontend feature (exact name match)

The cheapest signal for which frontend screens talk to which backend module.
Name-only match: the frontend feature and the app/ package with the same
basename. Does not replace reading the actual imports for a given feature.

- `attendance` <-> `attendance`
- `auth` <-> `auth`
- `dashboard` <-> `dashboard`
- `payroll` <-> `payroll`

Backend domains with no same-named frontend feature: `audit`, `employee`, `item`, `leave`, `notification`, `rbac`, `reports`, `user`
(A name mismatch here does not mean the domain is unused: `app/employee/` serves
routers for ~16 resources that each have their own frontend feature, and
`attendance`/`leave`/`rbac` back multiple differently-named feature screens.)

Frontend features with no same-named backend domain: `apps`, `blocks`, `categories`, `chats`, `daily-time-records`, `departments`, `divisions`, `dtr-adjustments`, `emp-tasks`, `employee-projects`, `employees`, `holidays`, `leave-calendar`, `leave-enrollment`, `leave-ledger`, `leave-policies`, `leave-requests`, `lots`, `model-types`, `models`, `owners`, `payroll-config`, `payroll-runs`, `payroll-settings`, `phases`, `positions`, `project-types`, `projects`, `roles`, `salary`, `settings`, `shifts`, `subdivisions`, `tasks`, `users`
(Many map to a differently-named backend domain, e.g. all `leave-*`/`holidays`
features hit `app/leave/`, and the CRUD screens under `app/employee/`;
`apps`/`chats`/`tasks`/`settings`/`users` are unwired template-demo features.)
