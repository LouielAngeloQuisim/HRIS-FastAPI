import uuid

from sqlmodel import SQLModel


class ModulePublic(SQLModel):
    id: uuid.UUID
    code: str
    name: str
    parent_id: uuid.UUID | None
    sort_order: int
    is_active: bool


class RolePublic(SQLModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_system: bool
    is_active: bool


class RolesPublic(SQLModel):
    data: list[RolePublic]
    count: int


class MyPermissions(SQLModel):
    """The caller's own effective permissions.

    Shaped as {module_code: {action: bool}} so the frontend can drive
    navigation without a second round trip, replacing the main_module /
    sub_module blocks the legacy login response carried.
    """

    role_code: str | None
    is_superuser: bool
    permissions: dict[str, dict[str, bool]]
