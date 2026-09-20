"""Central registry of routes that are intentionally reachable unauthenticated.

The legacy system's core failure was that authorization was opt-in: ~13.6% of
routes called `validateUserAccess`, and 15 controllers injected it and never
called it (roadmap §5). Nothing detected the gap.

Here the default is inverted. `tests/rbac/test_route_protection.py` walks every
registered route and fails unless it either requires authentication or appears
in the allowlist below. Exposing a new route publicly therefore requires an
explicit, reviewable entry in this file.
"""

# (HTTP method, path) pairs that may be called without credentials.
PUBLIC_ROUTES: set[tuple[str, str]] = {
    # Credential exchange. These cannot require a token by definition.
    ("POST", "/api/v1/login/access-token"),
    ("POST", "/api/v1/login/refresh-token"),
    # Logout authenticates via the refresh token in its body, not a header.
    ("POST", "/api/v1/logout"),
    # Password reset. Both are rate limited and neither reveals whether an
    # account exists.
    ("POST", "/api/v1/password-recovery/{email}"),
    ("POST", "/api/v1/reset-password/"),
    # Liveness probe. Returns a constant; leaks nothing.
    ("GET", "/api/v1/utils/health-check/"),
}

# Routes that are exempt because they are mounted only outside production.
# `/private/*` is a test-support router; app/api.py refuses to mount it unless
# ENVIRONMENT == "local".
LOCAL_ONLY_PREFIXES: tuple[str, ...] = ("/api/v1/private",)


def is_public(method: str, path: str) -> bool:
    return (method.upper(), path) in PUBLIC_ROUTES


def is_local_only(path: str) -> bool:
    return path.startswith(LOCAL_ONLY_PREFIXES)
