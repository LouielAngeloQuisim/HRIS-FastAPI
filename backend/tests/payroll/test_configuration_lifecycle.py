"""Statutory configuration lifecycle preserves historical rows."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.payroll.models import BIRBracket, PagIBIGBracket, PhilHealthBracket

CASES = [
    ('philhealth', PhilHealthBracket, {'salary_min': '10000', 'salary_max': '100000', 'rate': '5', 'employer_share': '2.5', 'employee_share': '2.5', 'effective_date': '2026-01-01'}),
    ('pagibig', PagIBIGBracket, {'salary_min': '1000', 'salary_max': '10000', 'employee_rate': '2', 'employer_rate': '2', 'effective_date': '2026-01-01'}),
    ('bir', BIRBracket, {'period': 'monthly', 'bracket_min': '100000', 'bracket_max': None, 'base_tax': '1234.56', 'excess_rate': '20', 'effective_date': '2026-01-01'}),
]


@pytest.mark.parametrize('slug,model,payload', CASES)
def test_configuration_update_and_deactivation(client: TestClient, db: Session, superuser_token_headers: dict[str, str], slug: str, model: type, payload: dict) -> None:
    url = f'{settings.API_V1_STR}/payroll/{slug}-brackets/'
    created = client.post(url, json=payload, headers=superuser_token_headers)
    assert created.status_code == 200, created.text
    identity = created.json()['id']
    updated = client.patch(f'{url}{identity}', json={**payload, 'effective_date': '2026-02-01'}, headers=superuser_token_headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()['effective_date'] == '2026-02-01'
    archived = client.delete(f'{url}{identity}', headers=superuser_token_headers)
    assert archived.status_code == 200, archived.text
    assert identity not in [row['id'] for row in client.get(url, headers=superuser_token_headers).json()]
    db.expire_all()
    row = db.get(model, uuid.UUID(identity))
    assert row is not None and row.is_deleted and not row.is_active
    assert row.deleted_at is not None
    assert client.patch(f'{url}{identity}', json=payload, headers=superuser_token_headers).status_code == 404
    assert client.delete(f'{url}{identity}', headers=superuser_token_headers).status_code == 404


@pytest.mark.parametrize('slug,model,payload', CASES)
def test_configuration_mutations_deny_unauthorized(client: TestClient, normal_user_token_headers: dict[str, str], slug: str, model: type, payload: dict) -> None:
    assert model in (PhilHealthBracket, PagIBIGBracket, BIRBracket)
    url = f'{settings.API_V1_STR}/payroll/{slug}-brackets/{uuid.uuid4()}'
    assert client.patch(url, json=payload, headers=normal_user_token_headers).status_code == 403
    assert client.delete(url, headers=normal_user_token_headers).status_code == 403


@pytest.mark.parametrize('slug,model,payload', CASES)
def test_inactive_configuration_is_not_used_by_calculator(db: Session, slug: str, model: type, payload: dict) -> None:
    from decimal import Decimal

    from app.payroll.calc import (
        StatutoryScheduleUnavailable,
        calculate_bir_tax,
        calculate_pagibig_employee_share,
        calculate_philhealth_employee_share,
    )

    row = model.model_validate({**payload, 'is_active': False})
    db.add(row)
    db.commit()
    calculators = {'bir': calculate_bir_tax, 'pagibig': calculate_pagibig_employee_share, 'philhealth': calculate_philhealth_employee_share}
    with pytest.raises(StatutoryScheduleUnavailable):
        if slug == 'bir':
            calculators[slug](db, Decimal('150000'), 'monthly', '2026-02-01')
        else:
            calculators[slug](db, Decimal('20000'), '2026-02-01')
    assert db.get(model, row.id) is not None
