# Remaining QA Execution Status

**Batch:** 1 — employee & leave workflows (QA-05, PAY-03, QA-04)
**Branch:** `fix/batch1-employee-leave-workflows` (from `origin/main` = 8cd0792)
**Base SHA:** 8cd0792a63a71466490863c619c5068028a50d04 (PR #74, QA-01/03/08 deployed)
**Head SHA:** TBD (updated each push)
**Owner:** Kilocode (implementation) | Codex (validation/merge/deploy)

**Checkpoint updated:** 2026-10-04 (Manila)

## Scope

| ID | Priority | Kind | Task | Status |
|---|---|---|---|---|
| QA-05 | P1 | GAP | Manual employee maintenance (create/edit/soft-archive) | IN_PROGRESS |
| PAY-03 | P1 | GAP | Employee salary setup + missing-salary empty state | PENDING |
| QA-04 | P1 | GAP | Leave policy + enrollment setup + request/approve/reject/cancel | PENDING |

## Prerequisites / blocked-by

- Backend for QA-05 already implemented (POST/PATCH/DELETE `/employees`).
- Backend for PAY-03 already implemented (`/payroll/employees/{id}/salary`, `/salaries/{id}`).
- Backend for QA-04 already implemented (LeavePolicy CRUD, enrollment, leave requests + approve/reject/cancel).
- No code changes in the merged PR #74 branch; preserving QA-01/03/08 regressions.
- `fix/deploy-ubuntu-2604` is superseded (its changes already on `origin/main`); not affected by this batch.

## Status details

### QA-05 - Manual employee maintenance (P1)
**Acceptance:** Create/edit/soft-archive supported core employee fields through UI. Preserve CSV import and profiles. Document deferred 201-file annexes accurately.
- Backend: complete (POST /employees, PATCH /employees/:id, DELETE /employees/:id; soft delete; ownership-protected annex read).
- Frontend TODO:
  - [ ] `lib/api/employees.ts`: createEmployee/updateEmployee/deleteEmployee mutations + query invalidation
  - [ ] `features/employees/components/resource-form.tsx`: create/edit Sheet form
  - [ ] `features/employees/components/employees-table.tsx`: Edit/Delete row actions + data-testid
  - [ ] `features/employees/index.tsx`: Add Employee button, modal, refetch on mutation
  - [ ] Tests: `resource-form.test.tsx`, update `index.test.tsx`
- Status: **IMPLEMENTING** (first files being written)

### PAY-03 - Employee salary setup prerequisite (P1)
**Acceptance:** Authorized effective-dated salary setup through UI; user can resolve missing-salary empty state. Prove one fictional employee reaches successful payroll review/generation in isolated QA.
- Backend: complete (create/update/list EmployeeSalary with effective_date; preview service throws "no active salary record" for missing rows — source of the empty state).
- Frontend TODO:
  - [ ] `lib/api/payroll.ts`: salary CRUD + hooks
  - [ ] `features/payroll/salary-setup/index.tsx`: effective-dated salary table + add/edit Sheet
  - [ ] Sidebar entry under Payroll
  - [ ] Missing-salary empty-state warning on payroll execution page
  - [ ] Tests: salary-setup page + permissions
- Status: **PENDING** (depends on employee list completeness)

### QA-04 - Leave policy and enrollment setup (P1)
**Acceptance:** Policy CRUD and employee enrollment through UI; complete fictional request, approval/rejection/cancellation, calendar and ledger journeys; meaningful empty states.
- Backend: complete (LeavePolicy CRUD incl. deactivate, enrollment POST/list, leave requests + approve/reject/cancel).
- Frontend TODO:
  - [ ] `lib/api/leave-policies.ts`: full CRUD + hooks
  - [ ] `features/leave-policies/index.tsx`: policy CRUD page
  - [ ] `features/leave-policies/components/policy-form.tsx` + `policy-delete-dialog.tsx`
  - [ ] Route `routes/_authenticated/leave-policies/index.tsx` + sidebar entry
  - [ ] `features/leave-enrollment/index.tsx`: employee ↔ policy enrollment UI
  - [ ] Tests: page + enrollment
- Status: **PENDING**

## Test strategy

- Targeted Vitest runs after each material change.
- Full gate (`scripts/verify.sh`) when the batch is complete.
- Full Playwright E2E suite at completion:
  - `e2e/hris/employees.spec.ts` → new create/edit/archive + reload/read-back
  - `e2e/payroll/execution.spec.ts` (new) → salary setup + preview with missing-salary + one complete generation
  - `e2e/leave-policies` / `e2e/leave-enrollments` (new) → policy CRUD + enrollment + request/approve/reject/cancel
  - Existing leave specs (leave-requests, leave-calendar, leave-ledger) re-run with real policy/enrollment data
- All writes to isolated QA data; no production CRUD.

## Validation status per ID

| ID | Backend done | Frontend done | Tests done | PR ready | Reviewed/deployed |
|---|---|---|---|---|---|
| QA-05 | ✅ | 🟡 in progress | ⏳ | ⏳ | ⏳ |
| PAY-03 | ✅ | ⏳ | ⏳ | ⏳ | ⏳ |
| QA-04 | ✅ | ⏳ | ⏳ | ⏳ | ⏳ |

## Known issues found during inspection (to fix in this batch)

- None identified yet; backend endpoints match the intended UI.
- Note: payroll salary update endpoint accepts `EmployeeSalaryCreate` body (preserved per backend contract).

## Next action

Write QA-05 employee create/edit/archive form + row actions, test, then proceed to PAY-03 salary setup and QA-04 leave policies/enrollment.
