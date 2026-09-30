"""Roadmap #81 — live 403 coverage for the four remaining authorization gaps.

`tests/rbac/test_route_protection.py` proves statically that every route carries
a PermissionChecker, and `test_require_permission.py` proves the dependency
fails closed on synthetic rbac modules. But four real CRUD domains had no test
that actually sends an authenticated request and observes HTTP 403:

  - /positions      -> module `emp_settings` (app/employee/routes.py positions_router)
  - /project-types  -> module `project_type`  (project_types_router)
  - /phases         -> module `phase`         (phases_router)
  - /model-types    -> module `model_types`   (model_types_router)

The (module, action) pairs come from the real `require_permission(...)` calls
in the shared `_make_crud_router` factory: GET list + GET by id need `view`,
POST needs `add`, PATCH needs `edit`, DELETE needs `delete`.

Pattern (mirrors tests/rbac/test_require_permission.py and
tests/leave/test_permissions.py): build a role that holds ONLY `view` on the
seeded module, bind a fresh non-superuser to it, log in for a real token, and
assert POST/PATCH/DELETE all return 403 with the expected module+action in the
detail. A second role holding nothing proves GET list itself is gated on
`view`; a third test proves the granted `view` returns 200 (positive control so
an always-403 bug cannot pass silently), plus one superuser control.
"""

import uuid
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.config.settings import settings
from app.rbac.models import Role, RolePermission
from app.rbac.selectors import get_module_by_code, get_role_by_code
from app.user.models import UserCreate
from app.user.services import create_user
from tests.utils.employee import create_subdivision
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR
NIL_UUID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def fresh_role(db: Session) -> Iterator[Callable[[str], Role]]:
    """Factory creating isolated Roles, torn down after each test."""

    created: list[Role] = []

    def _make(tag: str) -> Role:
        code = f"G81{tag}{uuid.uuid4().hex[:8]}"
        assert get_role_by_code(session=db, code=code) is None
        role = Role(code=code, name=f"gap81-{tag}")
        db.add(role)
        db.commit()
        db.refresh(role)
        created.append(role)
        return role

    yield _make

    for role in created:
        db.execute(
            delete(RolePermission).where(RolePermission.role_id == role.id)  # type: ignore[arg-type]
        )
        db.execute(delete(Role).where(Role.id == role.id))  # type: ignore[arg-type]
    db.commit()


def _grant_view(db: Session, role: Role, module_code: str) -> None:
    module = get_module_by_code(session=db, code=module_code)
    assert module is not None, f"module {module_code} must be seeded by init_db"
    db.add(RolePermission(role_id=role.id, module_id=module.id, can_view=True))
    db.commit()


def _viewer_user(client: TestClient, db: Session, role: Role) -> dict[str, str]:
    """Create a non-superuser bound to `role` and return its bearer headers."""
    password = random_lower_string()
    user = create_user(
        session=db,
        user_create=UserCreate(
            email=random_email(), password=password, is_superuser=False
        ),
    )
    user.role_id = role.id
    db.add(user)
    db.commit()
    db.refresh(user)

    r = client.post(
        f"{API}/login/access-token",
        data={"username": user.email, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _assert_403(r: httpx.Response, action: str, module: str) -> None:
    assert r.status_code == 403, r.text
    detail = r.json()["detail"].lower()
    assert module in detail and action in detail, detail


class Domain403Mixin:
    """Shared gate matrix for one CRUD domain.

    Subclasses provide MODULE, PREFIX, and create_payload(); optionally an
    `extra_payload_context` hook for FKs a valid create body requires.
    """

    MODULE: str
    PREFIX: str

    def create_payload(self) -> dict[str, Any]:
        raise NotImplementedError

    def test_write_and_read_actions_denied_per_missing_permission(
        self, client: TestClient, db: Session, fresh_role: Callable[[str], Role]
    ) -> None:
        # Role A holds view only: add/edit/delete each denied specifically.
        view_only = fresh_role("VW")
        _grant_view(db, view_only, self.MODULE)
        view_only_headers = _viewer_user(client, db, view_only)

        _assert_403(
            client.post(
                f"{self.PREFIX}/", json=self.create_payload(), headers=view_only_headers
            ),
            "add",
            self.MODULE,
        )
        # Unknown id is fine: the dependency runs before the handler, so 403
        # (not 404) proves the denial comes from the permission check.
        _assert_403(
            client.patch(
                f"{self.PREFIX}/{NIL_UUID}",
                json={"name": "x"},
                headers=view_only_headers,
            ),
            "edit",
            self.MODULE,
        )
        _assert_403(
            client.delete(
                f"{self.PREFIX}/{NIL_UUID}", headers=view_only_headers
            ),
            "delete",
            self.MODULE,
        )

        # Role B holds nothing: even the list GET is denied on view.
        no_perms = fresh_role("NONE")
        no_perms_headers = _viewer_user(client, db, no_perms)
        _assert_403(
            client.get(f"{self.PREFIX}/", headers=no_perms_headers),
            "view",
            self.MODULE,
        )

    def test_granted_view_returns_200(
        self,
        client: TestClient,
        db: Session,
        fresh_role: Callable[[str], Role],
        superuser_token_headers: dict[str, str],
    ) -> None:
        role = fresh_role("OK")
        _grant_view(db, role, self.MODULE)
        headers = _viewer_user(client, db, role)

        r = client.get(f"{self.PREFIX}/", headers=headers)
        assert r.status_code == 200, r.text

        r = client.get(f"{self.PREFIX}/", headers=superuser_token_headers)
        assert r.status_code == 200, r.text


class TestPositionsAuthorization403(Domain403Mixin):
    """/positions is gated by require_permission("emp_settings", action)."""

    MODULE = "emp_settings"
    PREFIX = f"{API}/positions"

    def create_payload(self) -> dict[str, Any]:
        return {"code": f"POS{uuid.uuid4().hex[:8]}", "title": "Gap-81 Tester"}


class TestProjectTypesAuthorization403(Domain403Mixin):
    """/project-types is gated by require_permission("project_type", action)."""

    MODULE = "project_type"
    PREFIX = f"{API}/project-types"

    def create_payload(self) -> dict[str, Any]:
        return {"code": f"PT{uuid.uuid4().hex[:8]}", "name": "Gap-81 Type"}


class TestPhasesAuthorization403(Domain403Mixin):
    """/phases is gated by require_permission("phase", action)."""

    MODULE = "phase"
    PREFIX = f"{API}/phases"

    def _payload(self, subdivision_id: uuid.UUID) -> dict[str, Any]:
        # Real subdivision id so a valid body is rejected with 403, not 422:
        # a schema error would mask the authorization outcome.
        return {
            "code": f"PH{uuid.uuid4().hex[:8]}",
            "name": "Gap-81 Phase",
            "subdivision_id": str(subdivision_id),
        }

    def test_write_and_read_actions_denied_per_missing_permission(
        self, client: TestClient, db: Session, fresh_role: Callable[[str], Role]
    ) -> None:
        subdivision = create_subdivision(db)
        self._subdivision_id = subdivision.id
        try:
            super().test_write_and_read_actions_denied_per_missing_permission(
                client, db, fresh_role
            )
        finally:
            db.delete(subdivision)
            db.commit()

    def create_payload(self) -> dict[str, Any]:
        return self._payload(self._subdivision_id)


class TestModelTypesAuthorization403(Domain403Mixin):
    """/model-types is gated by require_permission("model_types", action)."""

    MODULE = "model_types"
    PREFIX = f"{API}/model-types"

    def create_payload(self) -> dict[str, Any]:
        return {"code": f"MT{uuid.uuid4().hex[:8]}", "name": "Gap-81 Model Type"}
