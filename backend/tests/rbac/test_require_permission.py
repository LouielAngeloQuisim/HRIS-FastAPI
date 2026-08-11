"""Phase 0 required test #2 - "RBAC dependency: low-privilege token blocked from
a gated route".

The legacy system's authorization was opt-in and mostly absent (roadmap §5), so
these tests focus on the dependency failing *closed*: no role, wrong module,
wrong action, and inactive module must all deny.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.config.settings import settings
from app.rbac.models import Module, PermissionAction, Role, RolePermission
from app.rbac.services import get_effective_permissions, user_has_permission
from app.user.models import User, UserCreate
from app.user.services import create_user
from tests.utils.utils import random_email, random_lower_string

GATED_MODULES_ROUTE = f"{settings.API_V1_STR}/rbac/modules"
GATED_ROLES_ROUTE = f"{settings.API_V1_STR}/rbac/roles"


@pytest.fixture
def rbac_fixture(db: Session) -> Iterator[dict]:
    """Build an isolated module + two roles: one permitted, one not."""
    suffix = uuid.uuid4().hex[:8]

    module = Module(code=f"widgets_{suffix}", name="Widgets", sort_order=1)
    other_module = Module(code=f"gadgets_{suffix}", name="Gadgets", sort_order=2)
    db.add(module)
    db.add(other_module)
    db.commit()
    db.refresh(module)
    db.refresh(other_module)

    viewer_role = Role(code=f"VIEW_{suffix}", name="Viewer")
    editor_role = Role(code=f"EDIT_{suffix}", name="Editor")
    empty_role = Role(code=f"NONE_{suffix}", name="No Access")
    db.add(viewer_role)
    db.add(editor_role)
    db.add(empty_role)
    db.commit()
    db.refresh(viewer_role)
    db.refresh(editor_role)
    db.refresh(empty_role)

    # Viewer may only view; editor may view and edit but never delete.
    db.add(
        RolePermission(
            role_id=viewer_role.id, module_id=module.id, can_view=True
        )
    )
    db.add(
        RolePermission(
            role_id=editor_role.id,
            module_id=module.id,
            can_view=True,
            can_edit=True,
        )
    )
    db.commit()

    payload = {
        "module": module,
        "other_module": other_module,
        "viewer_role": viewer_role,
        "editor_role": editor_role,
        "empty_role": empty_role,
    }
    yield payload

    db.execute(
        delete(RolePermission).where(
            RolePermission.role_id.in_(  # type: ignore[union-attr]
                [viewer_role.id, editor_role.id, empty_role.id]
            )
        )
    )
    db.execute(
        delete(Role).where(
            Role.id.in_([viewer_role.id, editor_role.id, empty_role.id])  # type: ignore[union-attr]
        )
    )
    db.execute(
        delete(Module).where(Module.id.in_([module.id, other_module.id]))  # type: ignore[union-attr]
    )
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


class TestGatedRouteAccess:
    def test_low_privilege_token_is_blocked_from_gated_route(
        self, client: TestClient, db: Session, rbac_fixture: dict
    ) -> None:
        """The headline requirement for Phase 0."""
        user, password = _make_user(db, role_id=rbac_fixture["empty_role"].id)
        headers = _token_headers(client, user.email, password)

        r = client.get(GATED_MODULES_ROUTE, headers=headers)

        assert r.status_code == 403
        assert "permission" in r.json()["detail"].lower()

    def test_user_with_no_role_is_blocked(
        self, client: TestClient, db: Session
    ) -> None:
        """Deny by default: no role means no access."""
        user, password = _make_user(db, role_id=None)
        headers = _token_headers(client, user.email, password)

        r = client.get(GATED_MODULES_ROUTE, headers=headers)

        assert r.status_code == 403

    def test_unauthenticated_request_is_rejected(self, client: TestClient) -> None:
        r = client.get(GATED_MODULES_ROUTE)
        assert r.status_code == 401

    def test_superuser_is_allowed_through(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Guards the denial tests above against a false positive."""
        r = client.get(GATED_MODULES_ROUTE, headers=superuser_token_headers)
        assert r.status_code == 200

    def test_every_gated_route_rejects_the_low_privilege_token(
        self, client: TestClient, db: Session, rbac_fixture: dict
    ) -> None:
        user, password = _make_user(db, role_id=rbac_fixture["empty_role"].id)
        headers = _token_headers(client, user.email, password)

        for route in (GATED_MODULES_ROUTE, GATED_ROLES_ROUTE):
            assert client.get(route, headers=headers).status_code == 403, route

    def test_self_permission_route_is_open_to_any_authenticated_user(
        self, client: TestClient, db: Session, rbac_fixture: dict
    ) -> None:
        """Reading your own permissions is not privileged."""
        user, password = _make_user(db, role_id=rbac_fixture["viewer_role"].id)
        headers = _token_headers(client, user.email, password)

        r = client.get(f"{settings.API_V1_STR}/rbac/me/permissions", headers=headers)

        assert r.status_code == 200
        assert r.json()["role_code"] == rbac_fixture["viewer_role"].code


class TestPermissionCheckSemantics:
    def test_granted_action_is_allowed(
        self, db: Session, rbac_fixture: dict
    ) -> None:
        user, _ = _make_user(db, role_id=rbac_fixture["viewer_role"].id)

        assert user_has_permission(
            session=db,
            user=user,
            module_code=rbac_fixture["module"].code,
            action=PermissionAction.VIEW,
        )

    def test_ungranted_action_on_permitted_module_is_denied(
        self, db: Session, rbac_fixture: dict
    ) -> None:
        """Holding `view` must not imply `delete`."""
        user, _ = _make_user(db, role_id=rbac_fixture["viewer_role"].id)

        assert not user_has_permission(
            session=db,
            user=user,
            module_code=rbac_fixture["module"].code,
            action=PermissionAction.DELETE,
        )

    def test_permission_does_not_leak_across_modules(
        self, db: Session, rbac_fixture: dict
    ) -> None:
        user, _ = _make_user(db, role_id=rbac_fixture["editor_role"].id)

        assert not user_has_permission(
            session=db,
            user=user,
            module_code=rbac_fixture["other_module"].code,
            action=PermissionAction.VIEW,
        )

    def test_unknown_module_is_denied_not_allowed(
        self, db: Session, rbac_fixture: dict
    ) -> None:
        """The legacy switch returned a non-deny shape for unknown submodules."""
        user, _ = _make_user(db, role_id=rbac_fixture["viewer_role"].id)

        assert not user_has_permission(
            session=db,
            user=user,
            module_code="module_that_does_not_exist",
            action=PermissionAction.VIEW,
        )

    def test_inactive_module_denies_access(
        self, db: Session, rbac_fixture: dict
    ) -> None:
        module = rbac_fixture["module"]
        user, _ = _make_user(db, role_id=rbac_fixture["viewer_role"].id)
        module.is_active = False
        db.add(module)
        db.commit()

        try:
            assert not user_has_permission(
                session=db,
                user=user,
                module_code=module.code,
                action=PermissionAction.VIEW,
            )
        finally:
            module.is_active = True
            db.add(module)
            db.commit()

    def test_role_without_any_permission_rows_is_denied(
        self, db: Session, rbac_fixture: dict
    ) -> None:
        user, _ = _make_user(db, role_id=rbac_fixture["empty_role"].id)

        assert not user_has_permission(
            session=db,
            user=user,
            module_code=rbac_fixture["module"].code,
            action=PermissionAction.VIEW,
        )

    def test_superuser_bypasses_role_checks(self, db: Session) -> None:
        user, _ = _make_user(db, role_id=None, is_superuser=True)

        assert user_has_permission(
            session=db,
            user=user,
            module_code="anything-at-all",
            action=PermissionAction.DELETE,
        )


class TestEffectivePermissions:
    def test_reports_only_granted_modules(
        self, db: Session, rbac_fixture: dict
    ) -> None:
        user, _ = _make_user(db, role_id=rbac_fixture["editor_role"].id)

        effective = get_effective_permissions(session=db, user=user)

        assert rbac_fixture["module"].code in effective
        assert rbac_fixture["other_module"].code not in effective

    def test_reports_per_action_flags(
        self, db: Session, rbac_fixture: dict
    ) -> None:
        user, _ = _make_user(db, role_id=rbac_fixture["editor_role"].id)

        flags = get_effective_permissions(session=db, user=user)[
            rbac_fixture["module"].code
        ]

        assert flags == {"view": True, "add": False, "edit": True, "delete": False}

    def test_user_without_role_has_no_permissions(self, db: Session) -> None:
        user, _ = _make_user(db, role_id=None)

        assert get_effective_permissions(session=db, user=user) == {}
