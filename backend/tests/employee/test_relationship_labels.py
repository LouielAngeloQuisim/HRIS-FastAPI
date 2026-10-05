import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.employee.models import (
    EmployeeProjects,
    EmployeeRecords,
    Project,
    ProjectType,
    Subdivision,
)

API = settings.API_V1_STR


def project_fixture(db: Session, code: str, name: str, *, deleted: bool = False) -> Project:
    subdivision = Subdivision(subdivision_code=f'S-{code}', name=f'Subdivision {code}', location='Isolated QA')
    kind = ProjectType(code=f'T-{uuid.uuid4().hex[:8]}', name='Fixture type')
    db.add(subdivision)
    db.add(kind)
    db.commit()
    return Project(code=code, name=name, subdivision_id=subdivision.id, project_type_id=kind.id, is_deleted=deleted)


def test_labels_are_bounded_authorized_and_exclude_deleted(client: TestClient, db: Session, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str]) -> None:
    code = f'LABEL-{uuid.uuid4().hex[:8]}'
    project = project_fixture(db, code, 'Readable project')
    deleted = project_fixture(db, code+'-D', 'Deleted project', deleted=True)
    db.add(project)
    db.add(deleted)
    db.commit()
    url = f'{API}/projects/labels'
    response = client.get(url, params=[('ids', str(project.id)), ('ids', str(deleted.id)), ('ids', str(uuid.uuid4()))], headers=superuser_token_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {str(project.id): f'{code} — Readable project'}
    assert client.get(url, params={'ids': str(project.id)}, headers=normal_user_token_headers).status_code == 403
    assert client.get(url, params=[('ids', str(uuid.uuid4())) for _ in range(201)], headers=superuser_token_headers).status_code == 422


def test_assignment_label_resolves_employee_and_project_without_changing_ids(client: TestClient, db: Session, superuser_token_headers: dict[str, str]) -> None:
    code = uuid.uuid4().hex[:8]
    employee = EmployeeRecords(employee_code=f'E-{code}', first_name='Readable', last_name='Employee', birthdate=date(1990, 1, 1))
    project = project_fixture(db, f'P-{code}', 'Readable project')
    db.add(employee)
    db.add(project)
    db.commit()
    assignment = EmployeeProjects(employee_id=employee.id, project_id=project.id)
    db.add(assignment)
    db.commit()
    response = client.get(f'{API}/employee-projects/labels', params={'ids': str(assignment.id)}, headers=superuser_token_headers)
    assert response.status_code == 200, response.text
    assert response.json()[str(assignment.id)] == f'E-{code} — Readable Employee → P-{code} — Readable project'
    db.refresh(assignment)
    assert assignment.employee_id == employee.id
    assert assignment.project_id == project.id
    project.is_deleted = True
    db.add(project)
    db.commit()
    unavailable = client.get(f'{API}/employee-projects/labels', params={'ids': str(assignment.id)}, headers=superuser_token_headers)
    assert 'Unavailable project' in unavailable.json()[str(assignment.id)]
