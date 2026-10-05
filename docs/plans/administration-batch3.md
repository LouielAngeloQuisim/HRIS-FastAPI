# Administration Batch 3

Baseline origin/main: 4b94aac1539ab4ce558e77e85fc6d42ea8d2a39c (PR #75 deployed). Separate branch fix/batch3-administration-workflows.

Resolve QA-06 custom role lifecycle and QA-07 readable relationship labels. Add authorized role deactivation UI and server protection for system and assigned roles, including direct denied requests and concurrent role assignment safety. Resolve project/category/DTR adjustment/attendance/task related names through bounded shared queries; preserve original IDs and clear fallback for missing/deleted parents.

Tests: backend role lifecycle/permission/race tests, colocated frontend role and relationship tests, isolated UI deactivation and related-record journeys with reload/readback. Run scripts/verify.sh and full Playwright on the exact integrated head before publishing; integrate merged Batch 2 before final combined validation. Never modify production permissions/data.

Implementation covers unused-role deactivation, assigned/system protection, serialized assignment/deactivation, assigned-user counts, bounded per-resource labels and account-scoped query caching. IDs remain unchanged. Playwright verifies related labels after reload and role history/denied transitions.

Added `scripts/run-e2e-qa.sh`: one-command isolated browser runner, optional per-domain/spec filters, production URL/spec guards, shared QA container with a unique disposable database, owned servers, and restoration of the container's original state. It never reuses an unknown application server. Guard tests run before Docker access; full browser execution validates the runner itself.

Observed preliminary evidence: 7 focused backend tests (including two-session race), 33 frontend tests / 15 files, mypy 0 errors, targeted lint/typecheck clean. Integrate Batch 2 and run full gates/browser suite before claiming completion. No production permissions or records changed.

Final acceptance follow-up: all four statutory forms now use clear nonnegative-value and percentage-limit messages; PhilHealth and Pag-IBIG required-date errors now match SSS/BIR. Regression assertions preserve invalid numeric values and prevent mutation. The isolated runner supports Docker Desktop's standard Windows CLI when the WSL Linux link is unavailable. This closes the remaining PAY-08 wording gap without changing valid payloads or rates.
