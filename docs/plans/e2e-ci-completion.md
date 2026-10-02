# Full browser CI completion (#39)

Goal: execute every tracked browser spec against a fresh local API, frontend and disposable PostgreSQL database, using placeholder-only test identities. Align the job with Python 3.14 and Node 26.

Investigation found that the legacy 93 tests included nonasserting row-count checks, conditional edit/delete cases, invalid parent IDs, stale selectors and assertions against forms after successful closure. Replace dependent CRUD fragments with independent create/edit/delete journeys, strict HTTP assertions after redirects, and persisted API readback. Preserve all 25 domain spec files and the eight authentication/authorization tests. Do not skip failing journeys.

Integration testing exposed selected parent IDs being stripped by Zod, incorrect block/lot field names, empty numeric/boolean values sent as strings, unsupported holiday types, missing role codes and a holiday delete UI calling an absent API. Cover fixes with colocated browser tests and backend permission/persistence tests. Holiday deletion is soft and preserves historical instances.

The ledger page currently has no employee/policy selection. Its browser spec explicitly checks the shell and filter controls, not a working data journey; this remains a product gap for future module planning.

Validation: execute all 40 Playwright tests without retries against a newly created database; run scripts/verify.sh, workflow validation and GitHub CI. Record exact observed totals and production rollout in the PR. Failure reports retain placeholder-only browser artifacts for seven days. No production audit deletion or existing database modification is enabled.
