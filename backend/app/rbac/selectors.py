import uuid

from sqlmodel import Session, select

from app.rbac.models import Module, Role, RolePermission


def get_role_by_code(*, session: Session, code: str) -> Role | None:
    return session.exec(select(Role).where(Role.code == code)).first()


def get_role_by_id(*, session: Session, role_id: uuid.UUID) -> Role | None:
    return session.get(Role, role_id)


def get_module_by_code(*, session: Session, code: str) -> Module | None:
    return session.exec(select(Module).where(Module.code == code)).first()


def get_main_modules(*, session: Session) -> list[Module]:
    rows = session.exec(
        select(Module)
        .where(Module.parent_id.is_(None))  # type: ignore[union-attr]
        .order_by(Module.sort_order, Module.code)  # type: ignore[arg-type]
    ).all()
    return list(rows)


def get_submodules(*, session: Session, parent_id: uuid.UUID) -> list[Module]:
    rows = session.exec(
        select(Module)
        .where(Module.parent_id == parent_id)
        .order_by(Module.sort_order, Module.code)  # type: ignore[arg-type]
    ).all()
    return list(rows)


def get_all_modules(*, session: Session) -> list[Module]:
    rows = session.exec(
        select(Module).order_by(Module.sort_order, Module.code)  # type: ignore[arg-type]
    ).all()
    return list(rows)


def get_all_roles(*, session: Session) -> list[Role]:
    rows = session.exec(select(Role).order_by(Role.code)).all()  # type: ignore[arg-type]
    return list(rows)


def get_role_permission(
    *, session: Session, role_id: uuid.UUID, module_code: str
) -> RolePermission | None:
    """Fetch the permission row for a role against a module code."""
    return session.exec(
        select(RolePermission)
        .join(Module, Module.id == RolePermission.module_id)  # type: ignore[arg-type]
        .where(
            RolePermission.role_id == role_id,
            Module.code == module_code,
            Module.is_active.is_(True),  # type: ignore[union-attr]
        )
    ).first()


def get_permissions_for_role(
    *, session: Session, role_id: uuid.UUID
) -> list[tuple[Module, RolePermission]]:
    rows = session.exec(
        select(Module, RolePermission)
        .join(RolePermission, RolePermission.module_id == Module.id)  # type: ignore[arg-type]
        .where(RolePermission.role_id == role_id)
        .order_by(Module.sort_order, Module.code)  # type: ignore[arg-type]
    ).all()
    return [(module, permission) for module, permission in rows]
