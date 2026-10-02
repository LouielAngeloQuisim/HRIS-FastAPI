# Production UI QA and regression repairs

Owner request: manually exercise every website module through visible browser
forms and controls. Use only clearly labeled fictional QA records created in
this session; preserve existing records and retain review fixtures separately
from disposable deletion probes. No direct API record creation for this pass.

Confirmed defects to repair:
- Category form cannot supply code, project and phase; failed submissions are silent.
- Subdivision wizard tries to create a category before required parents and uses fake project type IDs; reorder to project then category and resume partial success without duplicate projects.
- Phase and block forms offer descriptions that the schemas discard.
- Lot Number is mapped to lot_name, while numeric lot_num stays empty; Description is discarded.
- Model type boolean appears blank despite persisting.
- Model type association was stripped by the model form schema.
- Employee CSV imports do not refresh the employee list.
- Fractional rendered hours reach integer backend fields without inline feedback.
- DTR edit controls are inert and its existing CSV importer is not exposed.
- Leave forms require raw IDs; calendar and ledger use a zero UUID rather than an employee selection.
- Optional adjustment dates send empty strings instead of being omitted.
- Generic module pages cannot open sidebar navigation on mobile; project types lack a navigation entry.

Validate fixes with typed payload assertions and real local browser journeys,
then full scripts/verify.sh, PR CI, merge, deployment, and manual production retest.
Keep the migration history intact and leave old Symfony work excluded.

Repairs expose existing backend workflows, preserve explicit UTC punch editing,
and show save errors inline. No production record writes use an API script.
Local automated tests use disposable database prerequisites only. Employee
edit/delete, role deletion, and leave-policy/enrollment setup still have no
existing production UI; those are workflow limitations to report honestly.

Local observed evidence: 707 backend tests, 291 Vitest tests in 92 files,
44 Playwright tests in 27 specs without retries. Regenerated MAP.md. The
final verification rerun follows the last wizard watch-value lint repair.
Manual production retest remains required after the PR deployment.
