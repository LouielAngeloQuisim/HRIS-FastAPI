"""The `require_permission(module, action)` dependency.

Roadmap §2.2: "A require_permission(module, action) dependency. Enforced on
every route (the original did not)."
"""

from typing import Any

from fastapi import Depends, HTTPException, Request, status

from app.common.audit.sink import SecurityEventType, log_security_event
from app.common.dependencies import CurrentUser, SessionDep
from app.rbac.models import PermissionAction
from app.rbac.services import user_has_permission
from app.user.models import User


class PermissionChecker:
    """Callable dependency that gates a route on one (module, action) pair.

    Implemented as a class so the module/action it guards stay introspectable
    on the route object - that is what lets the coverage test in
    tests/rbac/test_route_protection.py verify enforcement across the app.
    """

    def __init__(self, module: str, action: PermissionAction) -> None:
        self.module = module
        self.action = action

    def __call__(
        self, request: Request, session: SessionDep, current_user: CurrentUser
    ) -> User:
        if not user_has_permission(
            session=session,
            user=current_user,
            module_code=self.module,
            action=self.action,
        ):
            # Log permission denied
            client_ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            request_id = getattr(request.state, "request_id", None)

            log_security_event(
                security_event=SecurityEventType.PERMISSION_DENIED,
                user_id=str(current_user.id),
                user_email=current_user.email,
                ip_address=client_ip,
                user_agent=user_agent,
                request_id=request_id,
                module=self.module,
                action=self.action.value,
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "The user doesn't have permission to "
                    f"{self.action.value} {self.module}"
                ),
            )
        return current_user

    def __repr__(self) -> str:
        return f"PermissionChecker(module={self.module!r}, action={self.action.value!r})"


def require_permission(
    module: str, action: PermissionAction | str
) -> PermissionChecker:
    """Build a permission dependency.

    Accepts the action as an enum member or its string value so routes can be
    written as require_permission("emp_list", "view").
    """
    resolved = PermissionAction(action) if isinstance(action, str) else action
    return PermissionChecker(module=module, action=resolved)


def permission_dependency(
    module: str, action: PermissionAction | str
) -> Any:
    """Convenience wrapper for use in `dependencies=[...]`."""
    return Depends(require_permission(module, action))
