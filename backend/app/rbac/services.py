from sqlmodel import Session, select

from app.rbac.models import (
    Module,
    PermissionAction,
    Role,
    RoleCreate,
    RolePermission,
    RoleUpdate,
)
from app.rbac.selectors import (
    get_all_modules,
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
    permissions = update_dict.pop("permissions", None)

    db_role.sqlmodel_update(update_dict)
    session.add(db_role)

    if permissions is not None:
        _apply_role_permissions(session, db_role, permissions)

    session.commit()
    session.refresh(db_role)
    return db_role


def _apply_role_permissions(
    session: Session, role: Role, permission_strings: list[str]
) -> None:
    """Sync a role's permission rows from a list of "module.action" strings.

    Any module.action present in the list is granted; actions for a module
    that exist on the row but are absent from the list are revoked. Modules
    with no granted actions have their permission row removed entirely.
    """
    all_modules = {m.code: m for m in get_all_modules(session=session)}

    # Build {module_code: set_of_granted_actions}
    granted: dict[str, set[str]] = {}
    for entry in permission_strings:
        if "." not in entry:
            continue
        module_code, action = entry.rsplit(".", 1)
        if module_code not in all_modules or action not in ("view", "add", "edit", "delete"):
            continue
        granted.setdefault(module_code, set()).add(action)

    ACTION_COLS = {
        "view": "can_view",
        "add": "can_add",
        "edit": "can_edit",
        "delete": "can_delete",
    }

    # Upsert rows for modules that have at least one grant
    for module_code, actions in granted.items():
        module = all_modules[module_code]
        row = session.exec(
            select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.module_id == module.id,
            )
        ).first()
        if row is None:
            row = RolePermission(role_id=role.id, module_id=module.id)
        for action, col in ACTION_COLS.items():
            setattr(row, col, action in actions)
        session.add(row)

    # Remove rows for modules the role previously had but now has no grants for
    existing_rows = session.exec(
        select(RolePermission).where(RolePermission.role_id == role.id)
    ).all()
    for row in existing_rows:
        existing_module = session.get(Module, row.module_id)
        if existing_module is not None and existing_module.code not in granted:
            session.delete(row)


def delete_role(*, session: Session, db_role: Role) -> Role:
    """Soft delete: deactivate the role; never hard-delete (avoids orphaned users)."""
    db_role.is_active = False
    session.add(db_role)
    session.commit()
    session.refresh(db_role)
    return db_role
