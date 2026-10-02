# GET-route authentication completion (#81)

Exercise the registered FastAPI GET API routes through the real TestClient with missing and malformed bearer credentials. Parameterize from the registered route inventory so newly added routes are covered automatically. Keep the intentionally public health endpoint reachable. Local-only test-support routes are excluded consistently with the central route policy.

These behavioral checks supplement the existing static dependency-tree and permission-checker tests. Existing live module-level 403 tests remain in place. No production authorization behavior or public allowlist is changed.

Validation: run the complete scripts/verify.sh matrix against a disposable database and record exact counts in the PR. Confirm production deployment after merge.
