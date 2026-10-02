# Architecture and extension boundaries

The running system is a React/Vite application in frontendv3, served by Nginx, with a FastAPI API in backend and PostgreSQL 18. Traefik terminates HTTPS and routes the dashboard and API hosts. GitHub Actions builds commit-tagged images and deploys only after a PR merges.

Backend domains are packages with models, request/response schemas, routes, services and selectors. Register routers in backend/app/api.py. The employee package uses a CRUD router factory for sixteen resources; domains with business transitions keep explicit service methods. Share infrastructure through app/common rather than copying authorization, pagination or error handling.

Requests authenticate through the custom JWT dependencies. Authorization uses explicit module/action permissions, including row-level ownership where needed. Refresh tokens rotate once per use; the frontend client deduplicates concurrent refreshes. A new protected API route must pass the static route-policy and behavioral authentication checks.

Frontend feature pages live in src/features and use src/lib/api hooks for server state. Permission checks use view/add/edit/delete literals. Keep field names and values consistent with the backend schemas; browser tests must prove persisted results, not merely successful mock calls.

See [generated inventory](../MAP.md), [module guide](../modules/README.md), [development workflow](../feature-development-workflow.md), and [testing](../testing/README.md). Production procedures live in [runbooks](../runbooks/README.md).
