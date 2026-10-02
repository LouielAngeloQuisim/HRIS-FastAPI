# Finish-pass runtime and operational decisions

Date: 2026-10-02. Owner decisions were recorded in the implementation session.

The owner chose to include runtime migrations and deployment-action upgrades now. PR #68 upgrades Python to 3.14, Node to 26, Traefik to v3.7 and the reviewed actions. Local verification passed 519 backend tests and 270 frontend tests; production image builds, upgraded GitHub CI and deployment run 36980650229 all succeeded. Thirteen independently reviewed Dependabot proposals were confirmed closed after replacement deployment.

Audit retention keeps 90 days. Deletion remains disabled until the owner explicitly enables it. PR #66 introduced the bounded daily worker; PR #67 corrected Compose service placement and added parsing regression tests. The fixed rollout succeeded, with the worker running and API/frontend/Traefik health checks green. See [activation and backlog handling](../runbooks/audit-retention.md).

Full Playwright E2E CI and deeper deployment checks are required before starting new modules. E2E results belong in the implementation PR and STATUS; the existence of specs alone is not evidence of execution.
