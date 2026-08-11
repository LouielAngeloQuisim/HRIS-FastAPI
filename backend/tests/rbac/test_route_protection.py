"""Phase 0 / Item 4 - proof that authorization is enforced on *every* route.

Roadmap §5: "~13.6% of routes call validateUserAccess; 15 controllers inject it
but never call it. -> Enforce centrally." The point of this file is that the
gap is now detectable: adding an unprotected route fails the build unless it is
explicitly declared public in app/common/route_policy.py.
"""

from fastapi.routing import APIRoute

from app.common.route_policy import PUBLIC_ROUTES, is_local_only, is_public
from app.main import app
from app.rbac.dependencies import PermissionChecker

# Methods that never carry side effects or data.
IGNORED_METHODS = {"HEAD", "OPTIONS"}


def _iter_routes():
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(set(route.methods) - IGNORED_METHODS):
            yield method, route.path, route


def _requires_authentication(route: APIRoute) -> bool:
    """True if the route's dependency tree contains a security scheme.

    Covers get_current_user, get_current_active_superuser, and every
    require_permission dependency, since all of them ultimately depend on the
    OAuth2PasswordBearer scheme.
    """
    return bool(route.dependant.security_requirements) or any(
        sub.security_requirements
        for sub in _walk_dependencies(route)
    )


def _walk_dependencies(route: APIRoute):
    stack = list(route.dependant.dependencies)
    while stack:
        dependant = stack.pop()
        yield dependant
        stack.extend(dependant.dependencies)


def _permission_checkers(route: APIRoute) -> list[PermissionChecker]:
    found = []
    stack = list(route.dependant.dependencies)
    while stack:
        dependant = stack.pop()
        if isinstance(dependant.call, PermissionChecker):
            found.append(dependant.call)
        stack.extend(dependant.dependencies)
    return found


class TestRouteProtection:
    def test_every_route_is_protected_or_explicitly_public(self) -> None:
        unprotected = [
            f"{method} {path}"
            for method, path, route in _iter_routes()
            if not is_public(method, path)
            and not is_local_only(path)
            and not _requires_authentication(route)
        ]

        assert unprotected == [], (
            "These routes require neither authentication nor an explicit "
            "public declaration in app/common/route_policy.py: "
            f"{unprotected}"
        )

    def test_allowlist_has_no_stale_entries(self) -> None:
        """Keeps the allowlist honest as routes are renamed or removed."""
        live = {(method, path) for method, path, _ in _iter_routes()}
        stale = sorted(entry for entry in PUBLIC_ROUTES if entry not in live)

        assert stale == [], f"Stale PUBLIC_ROUTES entries: {stale}"

    def test_private_router_is_not_mounted_outside_local(self) -> None:
        """`/private/users/` creates users with no auth - it must stay local."""
        from app.config.settings import settings

        private_routes = [
            f"{method} {path}"
            for method, path, _ in _iter_routes()
            if path.startswith("/api/v1/private")
        ]

        if settings.ENVIRONMENT == "local":
            assert private_routes, "expected the private router in local env"
        else:
            assert private_routes == [], (
                f"private routes exposed in {settings.ENVIRONMENT}: {private_routes}"
            )

    def test_rbac_admin_routes_carry_a_permission_checker(self) -> None:
        """Authentication alone is not authorization."""
        gated = {
            ("GET", "/api/v1/rbac/modules"),
            ("GET", "/api/v1/rbac/roles"),
        }
        seen = set()

        for method, path, route in _iter_routes():
            if (method, path) in gated:
                checkers = _permission_checkers(route)
                assert checkers, f"{method} {path} has no PermissionChecker"
                seen.add((method, path))

        assert seen == gated, f"missing gated routes: {gated - seen}"

    def test_permission_checkers_declare_a_known_action(self) -> None:
        from app.rbac.models import PermissionAction

        for method, path, route in _iter_routes():
            for checker in _permission_checkers(route):
                assert isinstance(checker.action, PermissionAction), (
                    f"{method} {path} uses a non-enum action"
                )
                assert checker.module, f"{method} {path} has an empty module code"
