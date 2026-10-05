import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.common.security import get_password_hash
from app.config.settings import settings
from app.rbac.models import Role
from app.user.models import User

API = settings.API_V1_STR


@pytest.fixture(autouse=True)
def cleanup_lifecycle_fixtures(db: Session) -> Iterator[None]:
    yield
    db.rollback()
    for user in db.exec(select(User).where(col(User.email).like('lc-%@example.com'))).all():
        db.delete(user)
    db.commit()
    for role in db.exec(select(Role).where(col(Role.code).like('LC-%'))).all():
        db.delete(role)
    db.commit()


def test_unused_custom_role_deactivation_preserves_history(client: TestClient, db: Session, superuser_token_headers: dict[str, str]) -> None:
    role = Role(code=f'LC-{uuid.uuid4().hex[:8]}', name='Unused fixture')
    db.add(role)
    db.commit()
    response = client.delete(f'{API}/rbac/roles/{role.id}', headers=superuser_token_headers)
    assert response.status_code == 200
    db.refresh(role)
    assert not role.is_active
    assert db.get(Role, role.id) is not None


def test_assigned_role_is_protected_from_direct_deactivation(client: TestClient, db: Session, superuser_token_headers: dict[str, str]) -> None:
    role = Role(code=f'LC-{uuid.uuid4().hex[:8]}', name='Assigned fixture')
    db.add(role)
    db.commit()
    user = User(email=f'lc-{uuid.uuid4().hex}@example.com', hashed_password=get_password_hash('qa-placeholder'), role_id=role.id)
    db.add(user)
    db.commit()
    response = client.delete(f'{API}/rbac/roles/{role.id}', headers=superuser_token_headers)
    assert response.status_code == 409
    db.refresh(role)
    assert role.is_active
    roles = client.get(f'{API}/rbac/roles', headers=superuser_token_headers).json()['data']
    assert next(row for row in roles if row['id'] == str(role.id))['assigned_users'] == 1


def test_system_and_unauthorized_role_deactivation_rejected(client: TestClient, db: Session, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str]) -> None:
    role = Role(code=f'LC-S-{uuid.uuid4().hex[:8]}', name='System fixture', is_system=True)
    db.add(role)
    db.commit()
    url = f'{API}/rbac/roles/{role.id}'
    assert client.delete(url, headers=normal_user_token_headers).status_code == 403
    assert client.delete(url, headers=superuser_token_headers).status_code == 403
    db.refresh(role)
    assert role.is_active


def test_inactive_role_cannot_be_assigned(client: TestClient, db: Session, superuser_token_headers: dict[str, str]) -> None:
    role = Role(code=f'LC-{uuid.uuid4().hex[:8]}', name='Inactive fixture', is_active=False)
    user = User(email=f'lc-{uuid.uuid4().hex}@example.com', hashed_password=get_password_hash('qa-placeholder'))
    db.add(role)
    db.add(user)
    db.commit()
    response = client.post(f'{API}/users/{user.id}/role', json={'role_code': role.code}, headers=superuser_token_headers)
    assert response.status_code == 409
    db.refresh(user)
    assert user.role_id is None


def test_deactivation_and_assignment_race_never_leaves_an_assigned_inactive_role(db: Session) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from fastapi import HTTPException

    from app.rbac.services import delete_role
    from app.user.routes.users import RoleAssignIn, assign_user_role

    role = Role(code=f'LC-{uuid.uuid4().hex[:8]}', name='Race fixture')
    user = User(email=f'lc-{uuid.uuid4().hex}@example.com', hashed_password=get_password_hash('qa-placeholder'))
    db.add(role)
    db.add(user)
    db.commit()
    role_id, user_id, role_code = role.id, user.id, role.code
    bind = db.get_bind()
    barrier = Barrier(2)

    def deactivate() -> int:
        with Session(bind) as session:
            candidate = session.get(Role, role_id)
            assert candidate is not None
            barrier.wait(timeout=10)
            try:
                delete_role(session=session, db_role=candidate)
                return 200
            except HTTPException as error:
                session.rollback()
                return error.status_code

    def assign() -> int:
        with Session(bind) as session:
            barrier.wait(timeout=10)
            try:
                assign_user_role(session=session, user_id=user_id, body=RoleAssignIn(role_code=role_code), current_user=User(email='race-admin@example.com', hashed_password='placeholder', is_superuser=True))
                return 200
            except HTTPException as error:
                session.rollback()
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(deactivate), executor.submit(assign)]
        outcomes = [future.result(timeout=20) for future in futures]
    assert sorted(outcomes) == [200, 409]
    db.expire_all()
    saved_role = db.get(Role, role_id)
    saved_user = db.get(User, user_id)
    assert saved_role is not None and saved_user is not None
    assert saved_role.is_active or saved_user.role_id != saved_role.id
