# Frontend testing strategy

Mandatory test-selection, reliability, isolation and reporting rules are in the repository [test policy](../../docs/testing/test-policy.md). The operational commands and local browser setup are in the [testing runbook](../../docs/testing/README.md).

Use colocated Vitest browser tests for frontend behavior and Playwright under `e2e/` for critical workflows across the real UI/API/database boundary. Choose cases from the behavior and risk being changed; there is no required filename checklist, per-feature test count or coverage percentage. Reuse the existing `renderWithClient`, API hooks, E2E fixtures and page helpers before adding new abstractions.

Prefer accessible roles and labels for user-facing controls. Use stable `data-testid` selectors when a control's accessible contract is unsuitable or ambiguous. Avoid fixed sleeps; wait on observable UI or network outcomes. Keep API mocking at the existing hook boundary for component behavior tests, and use real disposable services for the integrated journeys that need to prove backend authorization or persistence.

Examples and counts from earlier planning snapshots are intentionally omitted; the policy and runbook describe current expectations without turning inventory into a quality target.
