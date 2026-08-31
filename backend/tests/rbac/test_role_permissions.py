"""Role permission persistence — PATCH /rbac/roles/{id} with a `permissions`
list, and GET /rbac/roles/{id}/permissions.

The frontend PermissionMatrix sends a flat list of "module.action" strings; the
backend must upsert RolePermission rows and expose the current state for
pre-populating the matrix.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.config.settings import settings
from app.rbac.models import Module, Role, RolePermission
from app.rbac.services import _apply_role_permissions
from app.user.models import UserCreate
from app.user.services import create_user
from tests.utils.utils import random_email, random_lower_string

ROLES_ROUTE = f"{settings.API_V1_STR}/rbac/roles"


@pytest.fixture
def perm_fixture(db: Session) -> Iterator[dict]:
    suffix = uuid.uuid4().hex[:8]

    division = Module(code=f"division_{suffix}", name="Division", sort_order=1)
    department = Module(code=f"department_{suffix}", name="Department", sort_order=2)
    db.add(division)
    db.add(department)
    db.commit()
    db.refresh(division)
    db.refresh(department)

    role = Role(code=f"PERM_{suffix}", name="Perm Role")
    db.add(role)
    db.commit()
    db.refresh(role)

    # Start with division.view already granted
    db.add(RolePermission(role_id=role.id, module_id=division.id, can_view=True))
    db.commit()

    payload = {"division": division, "department": department, "role": role}
    yield payload

    # Clean up permission rows, role, and modules
    db.exec(
        delete(RolePermission).where(RolePermission.role_id == role.id)  # type: ignore[union-attr]
    )
    db.delete(role)
    db.delete(division)
    db.delete(department)
    db.commit()


def _make_user(db: Session, *, role_id: uuid.UUID | None, is_superuser: bool = False):
    password = random_lower_string()
    user = create_user(
        session=db,
        user_create=UserCreate(
            email=random_email(), password=password, is_superuser=is_superuser
        ),
    )
    if role_id is not None:
        user.role_id = role_id
        db.add(user)
        db.commit()
        db.refresh(user)
    return user, password


def _token_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestApplyRolePermissionsUnit:
    def test_grants_and_revokes_correctly(self, db: Session, perm_fixture: dict) -> None:
        role = perm_fixture["role"]
        division = perm_fixture["division"]
        department = perm_fixture["department"]

        _apply_role_permissions(
            db, role, [
                f"{division.code}.view",
                f"{division.code}.add",
                f"{department.code}.edit",
            ]
        )
        db.commit()

        # division: view + add granted, edit + delete not
        div_row = db.exec(
            select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.module_id == division.id,
            )
        ).first()
        assert div_row is not None
        assert div_row.can_view is True
        assert div_row.can_add is True
        assert div_row.can_edit is False
        assert div_row.can_delete is False

        # department: only edit
        dept_row = db.exec(
            select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.module_id == department.id,
            )
        ).first()
        assert dept_row is not None
        assert dept_row.can_view is False
        assert dept_row.can_add is False
        assert dept_row.can_edit is True
        assert dept_row.can_delete is False

    def test_empty_list_removes_all_rows(self, db: Session, perm_fixture: dict) -> None:
        role = perm_fixture["role"]
        _apply_role_permissions(db, role, [])
        db.commit()

        rows = db.exec(
            select(RolePermission).where(RolePermission.role_id == role.id)
        ).all()
        assert len(rows) == 0

    def test_unknown_module_codes_are_ignored(self, db: Session, perm_fixture: dict) -> None:
        role = perm_fixture["role"]
        division = perm_fixture["division"]

        _apply_role_permissions(
            db, role, [
                f"{division.code}.view",
                "nonexistent_module.view",
                "malformed-no-dot",
            ]
        )
        db.commit()

        rows = db.exec(
            select(RolePermission).where(RolePermission.role_id == role.id)
        ).all()
        assert len(rows) == 1
        assert rows[0].module_id == division.id


class TestRolePermissionsEndpoints:
    def test_get_permissions_returns_current_state(
        self, client: TestClient, db: Session, perm_fixture: dict, superuser_token_headers: dict
    ) -> None:
        role = perm_fixture["role"]
        division = perm_fixture["division"]

        r = client.get(
            f"{ROLES_ROUTE}/{role.id}/permissions",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        assert r.json() == {"permissions": [f"{division.code}.view"]}

    def test_patch_with_permissions_persists_them(
        self, client: TestClient, db: Session, perm_fixture: dict, superuser_token_headers: dict
    ) -> None:
        role = perm_fixture["role"]
        division = perm_fixture["division"]
        department = perm_fixture["department"]

        r = client.patch(
            f"{ROLES_ROUTE}/{role.id}",
            json={
                "permissions": [
                    f"{division.code}.view",
                    f"{division.code}.add",
                    f"{department.code}.edit",
                ]
            },
            headers=superuser_token_headers,
        )
        assert r.status_code == 200

        # Verify via GET
        r2 = client.get(
            f"{ROLES_ROUTE}/{role.id}/permissions",
            headers=superuser_token_headers,
        )
        assert r2.status_code == 200
        perms = r2.json()["permissions"]
        assert f"{division.code}.view" in perms
        assert f"{division.code}.add" in perms
        assert f"{department.code}.edit" in perms

    def test_patch_without_permissions_leaves_them_unchanged(
        self, client: TestClient, db: Session, perm_fixture: dict, superuser_token_headers: dict
    ) -> None:
        role = perm_fixture["role"]
        division = perm_fixture["division"]

        # Update only name, no permissions field
        r = client.patch(
            f"{ROLES_ROUTE}/{role.id}",
            json={"name": "Updated Name"},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"

        # Permissions untouched
        r2 = client.get(
            f"{ROLES_ROUTE}/{role.id}/permissions",
            headers=superuser_token_headers,
        )
        assert r2.json() == {"permissions": [f"{division.code}.view"]}


class TestSystemRolePermissionProtection:
    """System roles (is_system=True) must not have their permissions mutated
    through the PATCH endpoint — the same block that guards name/description
    changes must also guard the new permissions field."""

    def test_patch_system_role_permissions_is_blocked(
        self, client: TestClient, db: Session, superuser_token_headers: dict
    ) -> None:
        """PATCHing permissions on a seeded system role (SADM) must return 403."""
        # Find the SADM system role
        from app.rbac.models import Role
        sadm = db.exec(select(Role).where(Role.code == "SADM")).first()
        assert sadm is not None, "SADM system role should be seeded"
        assert sadm.is_system is True

        # Get current permissions to verify they DON'T change
        r0 = client.get(
            f"{ROLES_ROUTE}/{sadm.id}/permissions",
            headers=superuser_token_headers,
        )
        assert r0.status_code == 200
        original_perms = set(r0.json()["permissions"])

        # Attempt to PATCH permissions on the system role
        r = client.patch(
            f"{ROLES_ROUTE}/{sadm.id}",
            json={"permissions": ["division.view"]},
            headers=superuser_token_headers,
        )
        assert r.status_code == 403
        assert "system" in r.json()["detail"].lower()

        # Verify permissions were NOT modified
        r2 = client.get(
            f"{ROLES_ROUTE}/{sadm.id}/permissions",
            headers=superuser_token_headers,
        )
        assert r2.status_code == 200
        assert set(r2.json()["permissions"]) == original_perms

    def test_patch_system_role_with_name_only_is_blocked(
        self, client: TestClient, db: Session, superuser_token_headers: dict
    ) -> None:
        """Confirm the existing system-role guard still works for name changes."""
        from app.rbac.models import Role
        sadm = db.exec(select(Role).where(Role.code == "SADM")).first()
        assert sadm is not None

        r = client.patch(
            f"{ROLES_ROUTE}/{sadm.id}",
            json={"name": "Hacked Name"},
            headers=superuser_token_headers,
        )
        assert r.status_code == 403


class TestPermissionRoundTrip:
    """Real persistence round-trip: PATCH then GET, asserting the saved set
    matches exactly — including that revoked permissions are gone, not just
    that granted ones appear. This is the test class that would have caught
    the original bug (a mocked api.patch returning {data: {}} would NOT catch
    a backend that silently drops the permissions field)."""

    def test_full_round_trip_exact_match(
        self, client: TestClient, db: Session, perm_fixture: dict, superuser_token_headers: dict
    ) -> None:
        """PATCH a role with a specific permission set, GET it back, assert exact match."""
        role = perm_fixture["role"]
        division = perm_fixture["division"]
        department = perm_fixture["department"]

        desired = [
            f"{division.code}.view",
            f"{division.code}.add",
            f"{department.code}.delete",
        ]

        # PATCH
        r = client.patch(
            f"{ROLES_ROUTE}/{role.id}",
            json={"permissions": desired},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200

        # GET back
        r2 = client.get(
            f"{ROLES_ROUTE}/{role.id}/permissions",
            headers=superuser_token_headers,
        )
        assert r2.status_code == 200
        returned = r2.json()["permissions"]

        # Exact match — no more, no less
        assert sorted(returned) == sorted(desired), (
            f"Round-trip mismatch: saved {sorted(desired)}, got {sorted(returned)}"
        )

    def test_revoked_permissions_are_actually_removed(
        self, client: TestClient, db: Session, perm_fixture: dict, superuser_token_headers: dict
    ) -> None:
        """Start with division.view granted, then PATCH with an empty list —
        the previously-granted permission must be gone, not still present."""
        role = perm_fixture["role"]
        division = perm_fixture["division"]

        # Verify we start with division.view
        r0 = client.get(
            f"{ROLES_ROUTE}/{role.id}/permissions",
            headers=superuser_token_headers,
        )
        assert f"{division.code}.view" in r0.json()["permissions"]

        # PATCH with empty list (revoke everything)
        r = client.patch(
            f"{ROLES_ROUTE}/{role.id}",
            json={"permissions": []},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200

        # GET — should be empty now
        r2 = client.get(
            f"{ROLES_ROUTE}/{role.id}/permissions",
            headers=superuser_token_headers,
        )
        assert r2.status_code == 200
        assert r2.json()["permissions"] == [], (
            f"Expected empty permissions after revoking all, got {r2.json()['permissions']}"
        )

    def test_partial_revocation_preserves_granted(
        self, client: TestClient, db: Session, perm_fixture: dict, superuser_token_headers: dict
    ) -> None:
        """Grant view+add, then PATCH with only view — add must be revoked while view stays."""
        role = perm_fixture["role"]
        division = perm_fixture["division"]

        # Start: grant view + add
        client.patch(
            f"{ROLES_ROUTE}/{role.id}",
            json={"permissions": [f"{division.code}.view", f"{division.code}.add"]},
            headers=superuser_token_headers,
        )

        # PATCH: only view (add should be revoked)
        r = client.patch(
            f"{ROLES_ROUTE}/{role.id}",
            json={"permissions": [f"{division.code}.view"]},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200

        # GET — view present, add gone
        r2 = client.get(
            f"{ROLES_ROUTE}/{role.id}/permissions",
            headers=superuser_token_headers,
        )
        perms = r2.json()["permissions"]
        assert f"{division.code}.view" in perms
        assert f"{division.code}.add" not in perms
        assert perms == [f"{division.code}.view"]
