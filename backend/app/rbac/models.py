"""RBAC entities.

The legacy model (`UserType` -> `MainModules` -> `SubModules`) stored every
permission as a serialized PHP array in a column per submodule: 5 columns on
`main_modules` and 24 on `sub_modules`. Adding a module meant a schema change,
and `SuperAdminController::updateMainModules()` passed 24 positional arguments
to `setPermissions()`, which is how the documented permission-corruption bug
happened (analysis/05 §B.10).

This replaces that with a normalised three-table design: modules form a
self-referencing tree, and permissions are rows rather than columns. Adding a
module is now data, not DDL.
"""

import uuid
from enum import Enum

from sqlmodel import Field, SQLModel, UniqueConstraint


class PermissionAction(str, Enum):
    """The four actions the legacy system tracked, kept 1:1."""

    VIEW = "view"
    ADD = "add"
    EDIT = "edit"
    DELETE = "delete"


# Maps an action onto its column on RolePermission.
ACTION_COLUMN: dict[PermissionAction, str] = {
    PermissionAction.VIEW: "can_view",
    PermissionAction.ADD: "can_add",
    PermissionAction.EDIT: "can_edit",
    PermissionAction.DELETE: "can_delete",
}


class Module(SQLModel, table=True):
    """A permissionable area of the app.

    `parent_id is None` denotes one of the top-level modules; everything else
    is a submodule of one of them.
    """

    __tablename__ = "module"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(unique=True, index=True, max_length=64)
    name: str = Field(max_length=128)
    parent_id: uuid.UUID | None = Field(
        default=None, foreign_key="module.id", index=True, ondelete="CASCADE"
    )
    sort_order: int = Field(default=0)
    is_active: bool = Field(default=True)

    @property
    def is_main_module(self) -> bool:
        return self.parent_id is None


class Role(SQLModel, table=True):
    """Replaces the legacy `UserType`.

    `code` is the legacy `user_code`. Unlike the original it is a real unique
    column - the legacy version had no DB constraint, so a duplicate could
    silently break `findOneBy(['user_code' => 'SUR'])` (analysis/05 §B.9).
    """

    __tablename__ = "role"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(unique=True, index=True, max_length=32)
    name: str = Field(max_length=128)
    description: str | None = Field(default=None, max_length=512)
    # System roles are seeded and must not be deleted by CRUD in later phases.
    is_system: bool = Field(default=False)
    is_active: bool = Field(default=True)


class RoleCreate(SQLModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)


class RoleUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    permissions: list[str] | None = Field(default=None)


class RolePermission(SQLModel, table=True):
    """One row per (role, module) pair."""

    __tablename__ = "role_permission"
    __table_args__ = (
        UniqueConstraint("role_id", "module_id", name="uq_role_permission_role_module"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    role_id: uuid.UUID = Field(
        foreign_key="role.id", index=True, nullable=False, ondelete="CASCADE"
    )
    module_id: uuid.UUID = Field(
        foreign_key="module.id", index=True, nullable=False, ondelete="CASCADE"
    )
    can_view: bool = Field(default=False)
    can_add: bool = Field(default=False)
    can_edit: bool = Field(default=False)
    can_delete: bool = Field(default=False)

    def allows(self, action: PermissionAction) -> bool:
        return bool(getattr(self, ACTION_COLUMN[action], False))
