# Security Policy

## Supported Versions

Only the current `main` branch is supported. Production is deployed by
merging pull requests into `main` (see `docs/runbooks/deploy.md`), so fixes
land via the normal PR flow.

## Reporting a Vulnerability

Please report security vulnerabilities **privately** through one of:

1. **GitHub Private Vulnerability Reporting** — open a report on this
   repository's **Security** tab ("Report a vulnerability"). This creates a
   private advisory and is the preferred channel.
2. If the form is unavailable, open a **private** issue or contact the
   repository owner (`LouielAngeloQuisim`) directly on GitHub — never through
   a public issue, discussion, or PR comment.

There is no dedicated security email address for this project; do not use
any email found in old git history or in the upstream FastAPI template —
this repository has been rewritten and is not affiliated with the upstream
template maintainers.

When reporting, include:

- Steps to reproduce (or example code / a proof-of-concept).
- The affected area (endpoint, module, configuration).
- Impact assessment and suggested fix, if you have one.

## Public Discussions

Please do not publicly discuss a potential vulnerability until a fix is
released or the report is closed as not applicable. This limits exposure
while the maintainers respond.

## Scope notes specific to this project

- Authentication is custom JWT (access + rotating single-use refresh token,
  cookies `hris_at`/`hris_rt`); RBAC is enforced per route via
  `require_permission` and the public-route allowlist in
  `backend/app/common/route_policy.py`. A route missing protection is a
  security bug — `backend/tests/rbac/test_route_protection.py` exists to
  catch it, but a discovered bypass should still be reported privately.
- Secrets and environment rules are documented in `AGENTS.md` §9. Historical
  template artifacts containing placeholder credentials are tracked as open
  cleanup items in `docs/ROADMAP.md` (#40/#88).
