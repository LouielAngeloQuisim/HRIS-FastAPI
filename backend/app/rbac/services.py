from sqlmodel import Session

from app.rbac.models import PermissionAction, Role, RoleCreate, RoleUpdate
from app.rbac.selectors import (
    get_permissions_for_role,
    get_role_permission,
)
from app.user.models import User


def user_has_permission(
    *, session: Session, user: User, module_code: str, action: PermissionAction
) -> bool:
    """Authoritative permission check.

    Deny-by-default: a user with no role, or a role with no row for the
    module, has no access. The legacy equivalent returned a *success* shape
    for unrecognised submodules in some branches and was only called by ~13.6%
    of routes (roadmap §5); here the check is centralised and fails closed.
    """
    # Platform superusers bypass role checks. This is the one intentional
    # difference from legacy, which modelled "super admin" as a role whose
    # flags happened to all be true. Keeping the flag lets the bootstrap
    # superuser administer the system before any role exists.
    if user.is_superuser:
        return True

    if user.role_id is None:
        return False

    permission = get_role_permission(
        session=session, role_id=user.role_id, module_code=module_code
    )
    if permission is None:
        return False

    return permission.allows(action)


def get_effective_permissions(
    *, session: Session, user: User
) -> dict[str, dict[str, bool]]:
    """Flatten a user's permissions into {module_code: {action: bool}}.

    Used by the login/bootstrap payload so the frontend can render navigation,
    mirroring the main_module/sub_module blocks the legacy login returned.
    """
    if user.role_id is None:
        return {}

    result: dict[str, dict[str, bool]] = {}
    for module, permission in get_permissions_for_role(
        session=session, role_id=user.role_id
    ):
        result[module.code] = {
            PermissionAction.VIEW.value: permission.can_view,
            PermissionAction.ADD.value: permission.can_add,
            PermissionAction.EDIT.value: permission.can_edit,
            PermissionAction.DELETE.value: permission.can_delete,
        }
    return result


def create_role(*, session: Session, role_in: RoleCreate) -> Role:
    db_role = Role.model_validate(role_in, update={"is_system": False, "is_active": True})
    session.add(db_role)
    session.commit()
    session.refresh(db_role)
    return db_role


def update_role(*, session: Session, db_role: Role, role_in: RoleUpdate) -> Role:
    update_dict = role_in.model_dump(exclude_unset=True)
    db_role.sqlmodel_update(update_dict)
    session.add(db_role)
    session.commit()
    session.refresh(db_role)
    return db_role


def delete_role(*, session: Session, db_role: Role) -> Role:
    """Soft delete: deactivate the role; never hard-delete (avoids orphaned users)."""
    db_role.is_active = False
    session.add(db_role)
    session.commit()
    session.refresh(db_role)
    return db_role
