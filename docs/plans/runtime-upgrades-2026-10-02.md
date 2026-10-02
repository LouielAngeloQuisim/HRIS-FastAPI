# Runtime and dependency upgrade evidence

This change replaces the thirteen open Dependabot proposals with updates tested together against the current main branch. Historical requirements.txt files are not restored.

| Proposal | Final replacement |
| --- | --- |
| #1 | Traefik v3.7 in development and production Compose |
| #2 | Python 3.14 production image and CI interpreter |
| #9 | python-multipart 0.0.32 |
| #18 | emails 1.1.3, typed Message import, sender and SMTP regression test |
| #27 | Node 26 production image and CI; install pinned pnpm directly because corepack is absent |
| #28 | prek 0.5.4 |
| #29 | pydantic-settings 2.15.0 |
| #30 | sentry-sdk 2.71.0 |
| #47 | actions/setup-node v7 |
| #48 | appleboy/ssh-action v1.2.5 |
| #49 | actions/checkout v7 |
| #50 | docker/setup-buildx-action v4 |
| #51 | pnpm/action-setup v6 with explicit version after Node setup |

The dependency lock selects compatible newer patch releases. Setup Node has no registry configuration in these workflows, so its removed dummy auth-token behavior is not used. The pnpm version is explicit to avoid depending on changed package-file inference.

Roadmap #77 removes unused reportlab and types-reportlab. PyMySQL remains required by ETL and its tests.

Validation performed on disposable databases, without production data or environment files:
- Initial full verification on Python 3.14: 517 backend tests and 270 frontend tests passed; mypy zero errors and migration drift zero.
- Production frontend Docker build on Node 26 passed.
- The final baseline includes the Compose deployment repair and its two regression tests. Final verification, CI and deployment results are recorded in the replacement PR.

Old Dependabot PRs are superseded only after the replacement passes checks, merges and deploys. This document does not assert that those steps have already happened.
