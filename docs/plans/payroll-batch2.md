# Payroll Batch 2

Baseline: origin/main 4b94aac1539ab4ce558e77e85fc6d42ea8d2a39c, including merged PR #75. Branch fix/batch2-payroll-workflows in /var/www/vhosts/hris-payroll-batch2.

Goal: resolve PAY-01/02/04–08 without changing statutory formulas or live rates. Correct monetary SSS inputs, nullable BIR upper limit and period/validation UX, supported configuration edit/deactivation and meaningful mutation errors, and nonpersistent preview with exactly-once generation.

Files: payroll backend services/routes/schemas/models and matching tests; payroll-config forms/pages/hooks/types, payroll execution page, colocated Vitest and payroll Playwright journeys. Add a migration only if a durable generation request identity requires one; preserve history and test migration round trip.

Tests: real disposable PostgreSQL verifies preview leaves no run/entry rows, generation retries/concurrency settle to one run, authorization and configuration lifecycle retain history. Browser journeys submit monetary amounts above 100, bounded/open BIR brackets, supported periods, edit/deactivate configuration, rejected mutations preserving form data, and salary-to-payroll review/generation. Use UI writes and real readback in isolated QA, no production writes.

Verification: focused tests after material changes, then scripts/verify.sh and full Playwright before publishing. Reuse the existing QA PostgreSQL container with a separate owned database. No retries/skips to hide failures.

Risks: preview currently commits rows despite its documented contract; callers use payroll_run_id, so preserve compatibility while distinguishing transient preview identity from persisted generation. Generation needs durable request identity scoped to authorization, payload-conflict handling and races. Configuration deletion must preserve references/history. Integrate reviewed Batch 1 once merged, then validate the exact combined head.

API compatibility: `POST /payroll/runs/generate` now requires a UUID `request_id`. Clients must retain this identity and the exact payload for retries after an unknown response. Reusing an identity with another actor or changed payload returns 409. Preview returns transient identities and never stores a run; generation stores its own durable identity. Existing runs remain readable with a null fingerprint. This prevents duplicates for one request identity, not separate intentionally-created requests.

Verification: scripts/verify.sh passed with 751 backend tests, 417 frontend tests / 117 files, no migration drift, types or lint errors. Migration downgrade/upgrade/check passed. Full Playwright first produced 63/64 with an attendance Close timeout; unchanged serial rerun passed 64/64 without retries. Final generation error-hook correction and its regression passed the repeated gate. Final full browser suite, including real 403 feedback, passed 65/65 without retries. No production rates or financial records changed.
