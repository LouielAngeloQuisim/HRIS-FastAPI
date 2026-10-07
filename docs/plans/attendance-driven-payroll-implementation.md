# Attendance-Driven Payroll Implementation

Status: in progress; not release-ready. Verification was run on 2026-10-07 against isolated local test data. No production data, production deployment, or real email delivery was used.

## Implemented in the current working branch

- Effective-dated employee shift assignments and Manila work dates, with UTC attendance timestamps and overnight shift attribution.
- Batch attendance import with server preflight/atomic commit, retained source/correction rows, duplicate employee/work-date and existing-record conflict detection, and recoverable import identities.
- Daily attendance interval revisions with overlap/date validation, actor/history records, a correction editor, and month/week/day/table views.
- Database guard for one active DTR per employee/work date; the migration aborts with duplicate record IDs and never rewrites legacy attendance.
- Overtime decisions record eligible and approved minutes, reason, reviewer and time; recalculation clears the prior decision and decision history is retained.
- Effective-dated employee pay-group assignments, configurable daily/twice-monthly/monthly schedules, versioned payroll-policy drafts and explicit confirmation.
- Missing-effective-salary roster filtering, employee compensation summary, and explicit selected-row bulk salary preflight/atomic commit.
- Payroll readiness endpoint and UI list expected employees with named salary, shift, pay-group, policy, attendance, pending-adjustment, overtime, duplicate and unscheduled-work blockers; responses are bounded and paginated.
- Legacy amount preview and draft generation are disabled because the old calculator has unsafe defaults and silent omissions. Historic runs remain readable, but statutory settings are drafts until confirmed. Automatic delivery and finalization have not been enabled.
- Duplicate same-employee/work-date CSV rows can be explicitly combined as intervals; missing-shift assignment is separately confirmed and audited. A merged day is not silently treated as several daily records.
- A Decimal/integer-minute attendance earnings calculator now handles hourly, daily, and monthly basis, approved overtime, explicit absence/paid-leave dispositions, monthly divisor, partial-day rule, and configured rounding. BIR bracket lookup uses one effective bracket and its cumulative base tax.
- The monthly-basis calculator was corrected so scheduled-period base is accrued for every scheduled date and unpaid absence is deducted once. It now aggregates and rounds the period once per consistent policy rather than rounding each date first. This prevents double absence deductions and daily rounding drift. An independent October 1–15, 2026 sample now gives ₱13,000.00 period base less ₱1,181.82 for one unpaid absence = ₱11,818.18 before statutory deductions; the API-level draft test verifies the same persisted figures and statutory blocker.
- The payroll page can create one idempotent, period-scoped attendance draft (up to 200 expected employees atomically), with source revisions, formulas, and named blockers. It deliberately adds a statutory-calculation blocker to every entry; the draft cannot enter review or be finalized.
- Review/finalization endpoints validate reviewer separation and snapshots. Finalization checks changed or newly added attendance, salary, shift/pay-group assignments, leave, holidays, policies and overlapping approved/paid runs. These guards are not a substitute for the missing complete calculation and are not reachable for the current blocked drafts.
- PostgreSQL outbox models and an opt-in worker create PDFs from frozen snapshots only after an authorized finalization; delivery is disabled by default. The worker treats ambiguous SMTP outcomes as uncertain rather than retrying automatically.

## Remaining before the requested workflow is complete

- Complete the calculation: taxable/non-taxable allowances; premium/holiday categories; lateness/undertime and partial-hour policy; month proration across effective salary/shift/policy boundaries; approved leave/holiday treatment; employment boundaries; statutory employee deductions and employer contributions; contribution-period/YTD balance and duplicate collection prevention; loan/adjustment rules; calculation trace for every line. The current draft gross is explicitly provisional and cannot be finalized.
- Build the real review screens and APIs for run/entry lists, expected roster, per-entry calculation/formulas, review/exclusion, stale-input rebuild, distinct final approval and authorized correction ledger. The current backend guards have no complete recalculate/review browser workflow.
- Freeze pay-group membership and each entry's source revisions when a prepared, fully calculated run is created; ensure all new/changed input rows reliably invalidate reviews and require recalculation. The draft creator is intentionally bounded at 200 people pending a safe scalable bulk transaction.
- Complete the profile compensation breakdown, salary/pay-group bulk workflows, and missing-salary recovery in payroll preparation.
- Independently validate current BIR, SSS, PhilHealth and Pag-IBIG obligations against official primary sources and company-specific timing; obtain HR-approved sample amounts and perform a parallel payroll comparison. Do not enable finalization before written acceptance.
- The BIR/SSS/PhilHealth/Pag-IBIG configuration pages exist and their saved rows feed the legacy table-based calculators, but they are not agency data feeds and no verified full effective-dated official schedules are loaded by default. The current attendance-driven draft does not apply these statutory tables and deliberately remains blocked. Before loading production-ready values, the exact employer population, member categories, tax annualization/YTD state, deduction timing, and current circular/table versions must be confirmed and independently reconciled. Source research on 2026-10-07 found the [SSS 2025 contribution schedule](https://www.sss.gov.ph/pay-contribution/) effective Jan 2025 (15% total, ₱35,000 max MSC, with employer-paid EC and MPF distinctions); PhilHealth's [official UHC contribution page](https://www.philhealth.gov.ph/uhc/) still displays 5% with ₱10,000/₱100,000 bounds but does not establish a new 2026 contribution circular; and [Pag-IBIG Circular 460](https://www.dbm.gov.ph/index.php/circular-letters?catid=335&id=2569%3Acircular-letter-no-2024-2&view=article) raises the maximum fund salary to ₱10,000 effective Feb 2024. The [BIR withholding calculator](https://web-services.bir.gov.ph/tax_calculator/wt_calculator.html) and [RR 11-2018](https://bir-cdn.bir.gov.ph/local/pdf/RR%20No.%2011-2018.pdf) demonstrate why the current single-bracket lookup is not enough to validate employee tax: taxable compensation types, payment frequency, MWE exemptions and year-end adjustment matter. These facts alone are insufficient for a safe import: category-specific schedules, rounding/collection timing and BIR cumulative withholding rules still need complete table-level validation.
- Finish secure payslip download/access auditing and delivery UI, test-mail-sink acceptance, scheduled worker lifecycle/monitoring, bounded retries, uncertain SMTP reconciliation, authorized address correction/resend and failure recovery. The opt-in worker/outbox is infrastructure groundwork only.
- Add integrated browser journeys and fault injection for the complete acceptance path, and test migration behavior against production-shaped data. Do not use production records or send real emails as test fixtures.

## Final verification gate

Verification completed on 2026-10-07 against isolated local test data:

- `bash scripts/verify.sh`: PASS (exit 0) after replacing the hanging `/dev/tcp` port probe with OS-assigned loopback port selection; 854 backend tests passed, 0 failed/skipped; Alembic upgrade and drift check passed; Ruff and mypy passed; TypeScript passed; 427 Vitest tests passed across 121 files; frontend build passed; `docs/MAP.md` was in sync.
- `bash scripts/run-e2e-qa.sh payroll`: 7/7 payroll Playwright journeys passed with one worker and zero retries against an isolated PostgreSQL database. This covers configuration CRUD for all four statutory pages and confirms the existing payroll preview/generation stays blocked with readiness explanations; it is not an end-to-end finalized payroll journey.
- ESLint reported 2 errors and 8 warnings; it remains report-only in the repository gate. Pytest reported 838 warnings. These results are reported rather than hidden.
- `git diff --check`: clean.
- ESLint reported 2 errors and 8 warnings; it is report-only per the current repository gate. These have not been represented as clean.

## Sample-company simulation and source status

The sample is intentionally hypothetical and non-statutory: monthly salary ₱26,000, 22-day divisor, 11 weekday shifts from October 1–15, 2026, one unpaid absence, no approved overtime or allowances. Expected gross period base is ₱13,000.00, attendance deduction ₱1,181.82, and provisional amount before mandatory deductions ₱11,818.18. It is a calculator regression example, not a real payroll or a legal company policy. Statutory deductions and finalization are omitted by design; the new run remains blocked.

These results verify the implemented and intentionally blocked behavior only. They do not establish payroll calculation correctness or production readiness.

Do not merge or deploy this implementation as a completed payroll phase. The requested end-to-end workflow is not complete: the persisted draft is explicitly provisional and blocked, statutory calculation and HR acceptance are missing, finalization cannot succeed, and the final review/finalization/delivery browser flow has not been implemented. Keep finalization and email delivery disabled until the missing calculations, HR-approved parallel sample comparison, integrated browser flow and fault-injection coverage pass.
