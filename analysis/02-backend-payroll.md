# Backend Payroll & Government-Contribution Business Logic — Analysis

**Project:** `/mnt/f/laragon/www/wchhris-api` (Symfony 7.0, PHP 8.2, Doctrine ORM)
**Scope:** Payroll generation, government dues (SSS / PhilHealth / Pag-IBIG), BIR tax, loans/advances, 13th-month, payslip, payroll groups, and report endpoints.
**Mode:** Read-only analysis. No source files were modified.

> All route paths below are exact (no class-level prefix is used on the payroll controllers except where noted). Symfony 7 attribute routing concatenates the class-route `name` (used as a prefix) with the method `name`; duplicate method `name`s collide in `RouteCollection` (last registration wins / one is dropped).

---

## 1. Controllers & Route Inventory

### 1.1 PayrollGenerationController (`src/Controller/PayrollGenerationController.php`)
No class-level `#[Route]`. All routes are exact method paths.

| Method | Path | Name | HTTP | Required input | Success |
|---|---|---|---|---|---|
| `create()` | `/api/generate-payroll` | `generate_payroll` | POST | `employee_id`, `date_start`, `date_end`, optional `salary_adjustment` + `sal_adj_*` keys | 201 `{message, data}` |
| `createPayrollPerEmployee()` | `/api/generate-payroll-for-all-employees` | `generate_all_payroll` | POST | `date_start`, `date_end`, optional `remarks` | 201 `{message}` |
| `createSalaryAdjustmentAndUpdatePayroll()` | `/api/update-payroll-deduction` | `update_payroll_deduction` | POST | `employee_id`, `payroll_id` | 201 `{message, data}` |
| `viewSalaryAdjustmentAndPayroll()` | `/api/view-salary-adjustment` | `view_salary_adjustment` | POST | `employee_id`, `payroll_id` | 201 `{message, data}` |

Error shape: `{'message': '...'}` with `HTTP_BAD_REQUEST` (400) / `HTTP_NOT_FOUND` (404). No `@IsGranted`, no `validateAccess` call → **no authorization on any payroll route**.

Private helpers: `calculateSSSDeductions`, `calculatePhilHealthDeduction`, `calculatePagIbigDeduction`, `calculateTaxDeduction`, `calculateLoanDeduction`, `deductLoans`, `createSalaryAdjustment`, `getOvertimeInDTRAdjustments`.

### 1.2 EmployeePayrollController (`src/Controller/EmployeePayrollController.php`)
| Method | Path | Name | HTTP |
|---|---|---|---|
| `createEmployeePayroll` | `/api/employee-payroll` | `create_employee_payroll` | POST |
| `getEmployeePayroll` | `/api/employee-payroll/{id}` | `get_employee_payroll` | GET |
| `listEmployeePayrolls` | `/api/employee-payroll` | `list_employee_payrolls` | GET |
| `updateEmployeePayroll` | `/api/employee-payroll/{id}` | `update_employee_payroll` | PUT |
| `deleteEmployeePayroll` | `/api/employee-payroll/{id}` | `delete_employee_payroll` | DELETE |
| `listEmployeesPayroll` | `/api/employees-payroll` | `api_employees_payroll_list` | GET |

Note: `createEmployeePayroll` is a **dumb passthrough** — it writes whatever `basic_salary`, `net_salary`, etc. the client sends (no recomputation). Anyone can fabricate payroll figures.

### 1.3 EmployeePayrollProfileController (`src/Controller/EmployeePayrollProfileController.php`)
| Method | Path | Name | HTTP |
|---|---|---|---|
| `saveEmployeePayrollProfile` | `/api/employee-payroll-profile/save` | `save_employee_payroll_profile` | POST, PUT |
| `createEmployeePayrollProfile` | `/api/employee-payroll-profile/create` | `create_employee_payroll_profile` | POST |
| `updateEmployeePayrollProfile` | `/api/employee-payroll-profile/update/{id}` | `update_employee_payroll_profile` | PUT |
| `getEmployeePayrollProfile` | `/api/employee-payroll-profile/find/{id}` | `get_employee_payroll_profile` | GET |

Private helpers (duplicated): `calculateSSSDeductions`, `calculatePhilHealthDeduction`, `calculatePagIbigDeduction`, `calculateTaxDeduction`, `calculateLoanDeduction`, `deductLoans`, `calculateEmployerSSSDeductions`, `calculateEmployerPhilHealthDeduction`, `calculateEmployerPagIbigDeduction`, `saveCashAdvance`, `saveSSSLoans`, `savePagibigLoans`.

### 1.4 PayslipController (`src/Controller/PayslipController.php`)
| Method | Path | Name | HTTP |
|---|---|---|---|
| `getPayroll` | `api/payslip` | `app_payslip` | POST |

Input `{payroll_id}`. Returns payroll + profile + **YTD** aggregations (see §7).

### 1.5 PayrollGroupsController (`src/Controller/PayrollGroupsController.php`)
| Method | Path | Name | HTTP |
|---|---|---|---|
| `list` | `/api/payroll-groups/list/{year}` | `payroll_groups_list` | GET |
| `show` | `/api/payroll-groups/find/{id}` | `payroll_groups_show` | GET |
| `create` | `/api/payroll-groups/create` | `payroll_groups_create` | POST |
| `update` | `/api/payroll-groups/update/{id}` | `payroll_groups_update` | PUT |
| `delete` | `/api/payroll-groups/delete/{id}` | `payroll_groups_delete` | DELETE |

### 1.6 Government-contribution config controllers
- **SSSController** `/api/sssconfig/{create,find/{id},list,update/{id},import,delete/{id}}` — CRUD + CSV-import (JSON `csv_data` array of rows; 13 columns indexed 0–12). Delete is **soft** (`setArchived(true)`).
- **PhilHealthController** `/api/philhealthconfig/{create,find/{id},list,update/{id},delete/{id}}`.
- **PagibigController** `/api/pagibigconfig/{create,find/{id},list,update/{id},delete/{id}}`.
- **BIRController (TaxConfig)** `/api/taxconfig/{create,get-taxconfig/{id},list,update/{id},delete/{id},import}` — import reads `row[0..4]`; delete nulls `taxContribution` on related profiles then removes.
- **TaxShieldController** `/tax_shield[/{id}]` CRUD (note: no `/api` prefix).

### 1.7 PayrollReportsController (`src/Controller/PayrollReportsController.php`)
All report routes are **GET with a JSON request body** `{dateFrom, dateTo}` (and `company_id` where noted). Each returns an array of employees with `payroll_details` taken from `EmployeePayrollRepository::findByPayrollProfileAndDateRange` (returns **one** payroll per profile in range — see §8).

| Path | Name | Notes |
|---|---|---|
| `/api/all-employee-payroll` | `api_employee_payroll_data` | **Ignores request body**; hardcodes `2023-10-01`→`2023-10-15` (BUG). |
| `/api/timesheet` | `get_timesheet_data` | Worker logs for active employees in range. |
| `/api/payrollsheet` | `get_all_employee_payroll_profiles` | Per-employee payroll + profile. |
| `/api/payrollsheet-with-taxshield` | `get_all_employee_payroll_profiles_with_taxshield` | + TaxShield. |
| `/api/payrollsheet-with-cash-advances` | `get_all_employee_payroll_profiles_with_cash_advances` | + cash-advance histories. |
| `/api/payrollsheet-with-salary-adjustment` | `get_all_employee_payroll_profiles_with_salary_adjustment` | + SalaryAdjustment. |
| `/api/gov-dues` | `get_gov_dues` | Per-employee gov dues. **Collides by name** with next route. |
| `/api/gov-total-dues` | `get_gov_dues` | Same name as above → **first route dropped** (BUG). Adds gov IDs. |
| `/api/company-gov-total-dues` | `get_company_gov_dues` | Aggregates one company (`company_id`). |
| `/api/get-payroll-summary` | `get_payroll_summary` | Aggregates all companies. |

There is **no Excel/CSV export** despite prior expectation — all responses are JSON.

### 1.8 Peripheral controllers
- **SalaryAdjustmentController** `/api/salary/adjustment` (POST), `/salary/adjustments` (GET list, uses serializer group `salary_adjustment`), `/salary/adjustment/{id}` (GET/PUT/DELETE).
- **AccountabilityRecordsController** class route `#[Route('/api/accountability_records', name:'delete_accountability_record', methods:['DELETE'])]`; methods `/list`,`/create`,`/find/{id}`,`/find-by-emp/{id}`,`/update/{id}`,`/archive/{id}`. **Name collisions:** `/find/{id}` & `/find-by-emp/{id}` both `show_accountability_record`; `/archive/{id}` & class route both `delete_accountability_record`.
- **ContractTypesController** `/api/contract-types/{list,create,find/{id},update/{id},delete/{id}}`.
- **AffiliatedCompanyController** `/api/affiliated-companies/{create,list,find/{id},update/{id},delete/{id}}`.

---

## 2. Payroll Calculation Pipeline (single employee — `create()`)

Order of operations (exact):

1. Validate `employee_id`, `date_start`, `date_end`.
2. Resolve `Worker` (`emp_record = employee_id`), then `User` → `Shift` (required).
3. Resolve `EmployeePayrollProfile` (`employee_record = employee_id`).
4. **Working metrics** (single path only):
   - `working_days_per_week = count(shift.daysOfWeek)`
   - `working_hours_per_day = shift.getTotalHoursMinusLunch() / 60`
   - `working_hours_per_month = (working_days_per_week * working_hours_per_day) * 4`  ← multiplied by **4**, not 4.33.
   - `minutesPerDay = 480` (hardcoded constant).
5. `workerLogs = WorkerLogs` in `[dateStart, dateEnd]` for the worker.
6. Accumulate:
   - `totalRenderedMinutes += log.renderedHours`
   - `totalApprovedOvertime += log.overtime * (log.overtimeApproved ? 1 : 0)`
   - `totalOvertime += log.overtime` (all, approved+unapproved)
   - `totalUndertime += log.undertime`
   - **`totalRenderedMinutes -= totalOvertime`** (overtime removed from regular minutes).
7. `total_calculated_overtime = (totalApprovedOvertime / 60) * profile.overtimeRate`
8. `total_calculated_undertime = (totalUndertime / 60) * profile.lateRate`
9. `basic_salary = profile.monthlySalary + profile.allowance`
10. `hourly_rate = round(basic_salary / working_hours_per_month, 2)`
11. `bi_weekly_salary = basic_salary / 2`
12. `totalRenderedDays = round(totalRenderedMinutes / 480, 2)`
13. `salaryPerDay = profile.dailyRate`
14. `salaryPerDayNonTax = profile.dailyRate + profile.dailyRateNonTax`
15. **Gross (taxable):**
    `salaryForRenderedDays = salaryPerDay * totalRenderedDays + (allowance/2) + total_calculated_overtime - total_calculated_undertime + salary_adjustment_taxable`
16. **Gross (non-tax):**
    `salaryForRenderedDaysNonTax = salaryPerDayNonTax * totalRenderedDays + (allowance/2) + total_calculated_overtime - total_calculated_undertime + salary_adjustment_nontax`
    *(In `create()` the non-tax portion uses `salary_adjustment_nontax`; in `update-payroll-deduction` and `view-salary-adjustment` it uses the raw `salary_adjustment` — INCONSISTENT.)*
17. `total_tax_shield = profile.dailyRateNonTax * totalRenderedDays`
18. Mandatory deductions (each `/2` to split across the two semi-monthly cutoffs):
    - `sss_deduction = calculateSSSDeductions(basic_salary, SSSConfig::findAll()) / 2`
    - `philhealth_deduction = calculatePhilHealthDeduction(basic_salary, …) / 2`
    - `hdmf_deduction = calculatePagIbigDeduction(basic_salary, …) / 2`
    - `total_mandatory_deduction = sss + philhealth + hdmf`
19. `total_loan_deduction = calculateLoanDeduction(profile)` (see §5 — **NOT halved**).
20. `tax_deduction = calculateTaxDeduction(salaryForRenderedDays - total_mandatory_deduction)` (semi-monthly bracketing, see §4).
21. `total_deduction = total_mandatory_deduction + tax_deduction + total_loan_deduction`
22. `net_salary = round(salaryForRenderedDaysNonTax - total_deduction, 2)`
23. Persist `EmployeePayroll` (all fields), `TaxShield` (`monthlyTaxShield = profile.allowanceNonTax`, `dailyTaxShield = profile.dailyRateNonTax`), call `deductLoans(...)`, `createSalaryAdjustment(...)`, then `flush()`.
24. **13th-month** accumulator (stored on `employeePayroll.thirteenthMonthPay`):
    - starts at 0
    - if `profile.includeSalaryAdjustmentForThirteenthMonth` → `+= salary_adjustment`
    - if `profile.includeSalaryForThirteenthMonth` → `+= salaryPerDay * totalRenderedDays`
    - if `profile.includeTaxshieldForThirteenthMonth` → `+= total_tax_shield`

---

## 3. Bulk generation (`createPayrollPerEmployee` / `/api/generate-payroll-for-all-employees`)

- Iterates **Active** `EmployeeRecords`.
- Requires `date_start`/`date_end`; if a `PayrollGroups` overlaps the range (`PayrollGroupsRepository::findByDateRange`) → returns `400 Payroll already exist`. Otherwise creates a `PayrollGroups`.
- Uses `PayrollCalculationConfig.no_hours_per_week * 4` as `working_hours_per_month` (shift is **ignored** — differs from single path).
- **Salary adjustment block is commented out** → adjustments are always 0 in bulk runs.
- Extra guard (absent in single path): `if (total_mandatory_deduction >= salaryForRenderedDays) total_mandatory_deduction = 0;` — zeroes *all* mandatory deductions when they exceed earnings (questionable).
- `flush()` inside the loop (per employee). Sends an HRS notification per employee (`Department` with `code = 'HRS'`); notification text is buggy: `$employee->Firstname()." ".$employee->Firstname()` (duplicate first name, no last name). `findOneBy(['code'=>'HRS'])` may return null → null deref.
- Returns only `{message}` (no per-employee data).

---

## 4. BIR Tax Formula (`calculateTaxDeduction`)

```
For each TaxConfig row:
    range_start = taxBracketRange / 2
    range_end   = taxBracketRangeEnd / 2
    if totalSalary > range_start AND totalSalary <= range_end:
        excess = totalSalary - range_start
        return round( (taxDeductionAmount / 2) + excess * (taxDeductionPercent / 100), 2 )
return 0
```

**Implication:** `TaxConfig` must store **annual** bracket bounds and the base `taxDeductionAmount`; generation halves both the bounds and the base amount to produce a **semi-monthly** tax. If no bracket matches (e.g., salary above the highest bracket), tax is **0** (wrong for high earners — no top-rate catch-all). The `>` on the lower bound is strict, so a salary exactly equal to `range_start` falls through.

**Inconsistency:** `EmployeePayrollProfileController::calculateTaxDeduction` (used by the profile *preview* `getEmployeePayrollProfile`) does **NOT** halve the brackets or the amount — it uses the stored annual values directly. So the preview tax ≠ the tax actually generated for the same salary.

---

## 5. Government Contribution Formulas

### SSS — `calculateSSSDeductions`
```
For each SSSConfig row:
    if basic_salary > round(rangeStart,2) AND basic_salary <= round(rangeEnd,2):
        return contributionTotalEe   // employee share
return 0
```
Brackets come from `SSSConfig::findAll()` (scanned linearly). Lower bound is strict `>`; salary exactly at `rangeStart` misses. Above all brackets → 0.

### PhilHealth — `calculatePhilHealthDeduction`
```
config = PhilHealthConfig::findOneBy([], ['id'=>'DESC'])   // latest
rate = config.employeeShare / 100
if basic_salary > config.minimumCap:
    return min(basic_salary, config.maximumCap) * rate
else:
    return config.minimumCap * rate
```
So PhilHealth never drops below `minimumCap * rate`. Employer variant uses `employerShare`.

### Pag-IBIG — `calculatePagIbigDeduction`
```
config = PagibigConfig::findOneBy([], ['id'=>'DESC'])
rate = config.employeeShare / 100
if basic_salary > 1500:
    return min(basic_salary, config.monthlyCompensationCap) * rate
else:
    return basic_salary * 0.01
```
The `1500` and `0.01` are **hardcoded magic numbers**. Employer variant uses `employerShare`.

**All three are divided by 2** in the generation pipeline (semi-monthly split). The profile-preview `calculate*` methods compute SSS/PhilHealth/Pag-IBIG **without `/2`** (called directly on the monthly `basic_salary`). So preview SSS/PhilHealth/Pag-IBIG ≠ generated (which are halved). Another preview-vs-generation mismatch.

---

## 6. Loan / Cash-Advance Amortization

### Planned deduction — `calculateLoanDeduction(profile)` (generation/reports)
```
sum over sssLoans:      if amount > 0  → min(deduction, amount)
sum over pagibigLoans:  if amount > 0  → min(deduction, amount)
sum over cashAdvances:  if amount > 0 OR isEnabled() → min(deduction, amount)
```
This is the amount *planned* to deduct and is added to `total_deduction`. **It is NOT halved** (unlike mandatory gov dues) — so the deduction amount is taken in full each payroll run. For semi-monthly payrolls this double-applies unless the configured `deduction` already represents a per-cutoff amount.

### Actual balance reduction — `deductLoans(profile, empRecord, newPayroll)` (generation `create()` path only)
- For each SSS/Pag-IBIG/CashAdvance with `amount > 0`: `deduction = min(deduction, amount)`; create a `*History` row; reduce the loan `amount` by `deduction`.
- Sums per `remark`: `sss_calamity_loan`, `sss_loan`, `hdmf_loan`, `hdmf_calamity`, `hdmf_mp2`, `total_ca`; writes them onto the `EmployeePayroll`.
- **Bug:** inside the Pag-IBIG loop the `if ($remark == 'hdmf_loan')` checks run **before** `$remark = $pagibigLoan->getRemark();` is assigned (line ~1049), so they test the *stale SSS `$remark`* from the previous loop. The `hdmf_loan`/`hdmf_calamity`/`hdmf_mp2` accumulators are effectively wrong.
- `update-payroll-deduction` and `view-salary-adjustment` have `deductLoans` **commented out**, so loans are neither reduced nor reflected in those runs.

---

## 7. Payslip & Year-To-Date (`PayslipController::getPayroll`)

Returns the `EmployeePayroll` (by `payroll_id`) plus the profile's government numbers and a `year_to_date` block computed over `Jan 1`–`Dec 31` of the payroll's `dateGenerated` year:
```
ytdGrossIncome += record.totalSalary
ytdSSS         += record.sssShare
ytdPhilHealth  += record.philhealthShare
ytdPagIbig     += record.hdmfContribution
ytdTax         += record.taxContribution
ytdNetPay      += record.netSalary
```
YTD gross = `totalSalary` (basic + OT + allowance), excludes loans/tax. Uses `findByPayrollProfileAndDateRangeList` (returns **all** payrolls in range, unlike the single-result variant).

---

## 8. Payroll Groups & Date-Range Lookup

`EmployeePayrollRepository::findByPayrollProfileAndDateRange` returns **one** `EmployeePayroll`:
```sql
WHERE payroll_profile = :id
  AND date_start >= :dateFrom
  AND date_end   <= :dateTo
ORDER BY date_start DESC LIMIT 1
```
Therefore every report endpoint returns at most one payroll per employee for the supplied range. For semi-monthly payrolls the caller must query each cutoff separately; a full-month range typically matches neither cutoff's strict `date_end <= dateTo` window. `PayrollGroups` exists only to block duplicate bulk runs (`findByDateRange` overlaps) and to group employees by cutoff.

`PayrollGroupsController::list` has a minor bug: inside the `array_map` closure it references `$payrolls` before initializing it when a group has zero employee payrolls (undefined-variable warning).

---

## 9. Data Model Notes (key entities)

- **EmployeePayroll**: `basic_salary, overtime_salary, total_salary, total_deduction, net_salary, thirteenth_month_pay, sss_share, philhealth_share, hdmf_contribution, insurance_contribution, tax_contribution, cash_advance_deduction, undertime_deduction, rendered_days, total_tax_shield, total_ca, sss_calamity_loan, sss_loan, hdmf_loan, hdmf_calamity_loan, hdmf_mp2, date_start, date_end, date_generated`; relations: `payroll_profile`, `payroll_group`, one-to-one `TaxShield`.
- **EmployeePayrollProfile**: `monthly_salary, allowance, allowance_non_tax, daily_rate, daily_rate_non_tax, hourly_rate, overtime_rate, late_rate, sss_loan, sss_loan_deduction, hdmf_loan, hdmf_loan_deduction, cash_advance, cash_advance_deduction, other_loans, other_loans_deduction, employer_sss_contribution, employer_pagibig_contribution, employer_philhealth_contribution, accident_insurance, thirteenth_month_pay`; flags `includeSalaryAdjustmentForThirteenthMonth`, `includeSalaryForThirteenthMonth`, `includeTaxshieldForThirteenthMonth`; relations to `SSSConfig`, `TaxConfig`, `PagibigConfig`, `PhilHealthConfig`, and loan collections.
- **Loan/History entities**: `SSSLoans`/`SSSLoansHistory`, `PagibigLoans`/`PagibigLoansHistory`, `CashAdvance`/`CashAdvanceHistory`, `LoanHistory` (almost empty repository, only created, never queried meaningfully).
- **Config entities**: `SSSConfig` (range_start/end, msc_ec/wisp/total, regular_er/ee, ec_er/ee, wisp_er/ee, total_er/ee), `PhilHealthConfig` (base_rate, employee_share, employer_share, minimum_cap, maximum_cap), `PagibigConfig` (employer_share, employee_share, monthly_compensation_cap), `TaxConfig` (name, range, range_end, percent, amount), `PayrollCalculationConfig` (only `no_hours_per_week`).
- **HolidayConfig** exists with `multiplier_regular`/`multiplier_overtime` but is **never referenced** in payroll generation → no holiday/rest-day/night-diff pay is applied.

---

## 10. Bugs, Hacks & Weak Spots (reimplementation risks)

1. **No authorization** — `UserAccessValidation` is injected into payroll controllers but never invoked; payroll/loan/SSS-config endpoints are unprotected.
2. **`saveEmployeePayrollProfile` zeroes all loan balances** (`setSssLoan(0)`, `setHdmfLoan(0)`, `setCashAdvance(0)`, `setOtherLoans(0)`, and their deductions) on every save. If the client omits the loan arrays, balances are wiped.
3. **`/api/all-employee-payroll` ignores its input** and always filters to `2023-10-01`–`2023-10-15`.
4. **Route-name collisions** → dropped endpoints:
   - `PayrollReportsController`: `/api/gov-dues` and `/api/gov-total-dues` share `name: get_gov_dues` → `/api/gov-dues` is unreachable.
   - `AccountabilityRecordsController`: `/find/{id}` & `/find-by-emp/{id}` share `show_accountability_record`; `/archive/{id}` & class route share `delete_accountability_record`.
5. **Preview ≠ generation** — `getEmployeePayrollProfile` computes SSS/PhilHealth/Pag-IBIG and BIR tax **without the `/2` semi-monthly halving** that `PayrollGenerationController` applies. Preview figures will not match the generated payroll.
6. **Loan deduction not halved** while gov dues are halved → inconsistent per-cutoff application (potential double deduction of loans).
7. **`deductLoans` Pag-IBIG remark bug** (stale `$remark`) → wrong `hdmf_loan`/`hdmf_calamity`/`hdmf_mp2` classification.
8. **`view-salary-adjustment` mutates data** — it persists the recomputed `EmployeePayroll` and creates a new `SalaryAdjustment` row on every call (duplicate SA rows).
9. **`createSalaryAdjustment` requires unvalidated keys** (`sal_adj_regular_ndot_hours`, `sal_adj_regular_ndot_pay`, `sal_adj_ot_meal_subsidy_days`, `sal_adj_ot_meal_subsidy_amount`, `sal_adj_4hrs_more_weekend_holiday`, `sal_adj_amount`, `sal_adj_temp_allowance`, `sal_adj_wellness`, `sal_adj_total_nontax_salary`, `sal_adj_total_tax_salary`, `sal_adj_total_salary`); missing keys yield null/warning.
10. **No DB transactions** around the multi-entity writes (payroll + tax shield + loans + histories). `deductLoans` flushes internally; partial failure can leave payroll persisted while loans un-deducted (or vice-versa).
11. **Tax top bracket missing** → returns 0 above highest `TaxConfig` row.
12. **SSS strict `>` lower bound** → salary equal to a bracket's `rangeStart` is skipped.
13. **Hardcoded magic numbers**: `minutesPerDay = 480`, `*4` weeks/month, Pag-IBIG `1500`/`0.01`, fallback dates `2023-10-01/15`, department code `'HRS'`.
14. **No holiday/rest-day/OT-multiplier logic** despite `HolidayConfig` existing; OT is a flat `approvedOvertime(hrs) * overtimeRate`.
15. **`createEmployeePayroll` passthrough** lets clients write arbitrary payroll amounts.
16. **Dead code**: `PayrollReportsController`'s private `calculate*` methods are never called by any report (reports read stored `EmployeePayroll`); they are duplicate, drift-prone copies of the generation logic.
17. **Notification bug**: duplicate first name, missing last name in HRS notification text.

---

## 11. Reimplementation Checklist

To rebuild payroll exactly:
- Keep `TaxConfig` rows as **annual** values; halve bounds + base amount per cutoff.
- Apply `/2` to SSS/PhilHealth/Pag-IBIG employee shares per cutoff; loans **not** halved.
- Use `minutesPerDay=480`, `working_hours_per_month = working_days_per_week * (shift_hours_minus_lunch/60) * 4` (single) or `PayrollCalculationConfig.no_hours_per_week * 4` (bulk).
- Subtract total overtime from rendered minutes; OT pay = approved overtime only × `overtimeRate`; undertime = undertime × `lateRate`.
- Gross taxable = `dailyRate*renderedDays + allowance/2 + OT - UT + taxable_adjustment`; non-tax = `(dailyRate+dailyRateNonTax)*renderedDays + allowance/2 + OT - UT + nontax_adjustment`.
- 13th-month = sum of enabled components (`dailyRate*renderedDays`, `salary_adjustment`, `total_tax_shield`).
- Persist `EmployeePayroll`, `TaxShield`; reduce loan balances via `deductLoans` (fix the Pag-IBIG remark ordering); create `SalaryAdjustment` with all 11 keys.
- Reports: single payroll per profile per range (`date_start>=from AND date_end<=to`); YTD = Jan1–Dec31 by `dateGenerated` year.
- Fix the listed collisions, the preview/generation mismatch, the profile-save loan wipe, and add authorization + transactions before production use.
