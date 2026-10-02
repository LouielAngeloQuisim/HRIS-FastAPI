# Existing modules and adding a module

Use [MAP](../MAP.md) for the generated endpoint, permission, feature and migration inventory. The source code remains authoritative when older phase trackers lag.

| Domain | Responsibility and extension point |
| --- | --- |
| employee | Employees, organization and construction/manpower resources; CRUD router factory plus ownership-aware annex and attachment operations |
| auth / user / rbac | Credential exchange, users, roles, module permissions and policy dependencies |
| attendance | Shifts, daily time records and approval of adjustments |
| leave | Policies, enrollments, requests, ledger entries and holidays |
| payroll | Salary history, statutory tables, calculators and payroll runs |
| audit / notification | Operational audit records and user notifications |
| reports / dashboard | Read projections and dashboard metrics |
| common / config | Shared API conventions, security dependencies, settings and database setup |

For a new module:
1. Write a plan naming business states, actor permissions, ownership rules, fields and expected API errors.
2. Add a domain package and register its router; add Alembic migrations for persistent models.
3. Seed any required RBAC modules and permissions explicitly; avoid making authentication opt-in.
4. Add feature pages and API hooks, preserving backend field names and numeric/boolean types.
5. Add domain pytest coverage, colocated Vitest browser tests and a self-contained Playwright journey with valid disposable prerequisites.
6. Regenerate MAP, run full verification and E2E, publish a PR, then validate the deployment.

Known product gaps remain explicit: employee CRUD and attachment UI are deferred; leave-ledger employee/policy selection is not implemented. Its E2E shell test does not claim a working ledger-data journey. Mock template pages for apps/chats/tasks/users/settings do not constitute HRIS modules. Plan these separately when defining new work.
