"""RBAC introspection + Role (UserType) CRUD.

Phase 0 kept this read-only. Phase 1 adds Role CRUD gated by enforced RBAC, plus
the privilege-escalation guarantees (role changes only via the dedicated
/user/{id}/role endpoint, and Role is never hard-deleted).
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.common.dependencies import CurrentUser, SessionDep
from app.rbac.dependencies import require_permission
from app.rbac.models import RoleCreate, RoleUpdate
from app.rbac.schemas import ModulePublic, MyPermissions, RolePublic
from app.rbac.selectors import (
    get_all_modules,
    get_all_roles,
    get_role_by_code,
    get_role_by_id,
)
from app.rbac.services import (
    create_role,
    delete_role,
    get_effective_permissions,
    update_role,
)

router = APIRouter(prefix="/rbac", tags=["rbac"])


@router.get(
    "/modules",
    response_model=list[ModulePublic],
    dependencies=[Depends(require_permission("administration", "view"))],
)
def read_modules(session: SessionDep) -> Any:
    return get_all_modules(session=session)


@router.get(
    "/roles",
    response_model=list[RolePublic],
    dependencies=[Depends(require_permission("administration", "view"))],
)
def read_roles(session: SessionDep) -> Any:
    return get_all_roles(session=session)


@router.post(
    "/roles",
    response_model=RolePublic,
    status_code=201,
    dependencies=[Depends(require_permission("administration", "add"))],
)
def create_role_route(*, session: SessionDep, role_in: RoleCreate) -> Any:
    existing = get_role_by_code(session=session, code=role_in.code)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Role code already exists")
    db_role = create_role(session=session, role_in=role_in)
    return RolePublic.model_validate(db_role)


@router.patch(
    "/roles/{role_id}",
    response_model=RolePublic,
    dependencies=[Depends(require_permission("administration", "edit"))],
)
def update_role_route(*, session: SessionDep, role_id: uuid.UUID, role_in: RoleUpdate) -> Any:
    db_role = get_role_by_id(session=session, role_id=role_id)
    if db_role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if db_role.is_system:
        raise HTTPException(status_code=403, detail="System roles cannot be edited")
    return RolePublic.model_validate(update_role(session=session, db_role=db_role, role_in=role_in))


@router.delete(
    "/roles/{role_id}",
    dependencies=[Depends(require_permission("administration", "delete"))],
)
def delete_role_route(session: SessionDep, role_id: uuid.UUID) -> Any:
    db_role = get_role_by_id(session=session, role_id=role_id)
    if db_role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if db_role.is_system:
        raise HTTPException(status_code=403, detail="System roles cannot be deleted")
    delete_role(session=session, db_role=db_role)
    return {"detail": "Role deleted successfully"}


@router.get("/me/permissions", response_model=MyPermissions)
def read_my_permissions(session: SessionDep, current_user: CurrentUser) -> Any:
    """Any authenticated user may read their own permissions."""
    role_code = None
    if current_user.role_id is not None:
        from app.rbac.models import Role

        role = session.get(Role, current_user.role_id)
        role_code = role.code if role else None

    return MyPermissions(
        role_code=role_code,
        is_superuser=current_user.is_superuser,
        permissions=get_effective_permissions(session=session, user=current_user),
    )
