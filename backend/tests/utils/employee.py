"""Factory helpers for Phase 1 test data.

Builders write directly through the service layer (not the HTTP API) so tests
can set up deep dependency chains cheaply, then exercise the API for the
behaviour under test.
"""

import uuid

from sqlmodel import Session

from app.employee import models as m
from app.employee import schemas as s
from app.employee.services import create_obj
from tests.utils.utils import random_lower_string


def _code() -> str:
    return f"{random_lower_string()[:8]}{uuid.uuid4().hex[:6]}"


def create_division(db: Session, *, name: str | None = None) -> m.Division:
    return create_obj(
        session=db,
        model=m.Division,
        data=s.DivisionCreate(code=_code(), name=name or "Test Division"),
    )


def create_department(db: Session, division_id: uuid.UUID) -> m.Department:
    return create_obj(
        session=db,
        model=m.Department,
        data=s.DepartmentCreate(code=_code(), name="Test Department", division_id=division_id),
    )


def create_subdivision(db: Session) -> m.Subdivision:
    return create_obj(
        session=db,
        model=m.Subdivision,
        data=s.SubdivisionCreate(
            subdivision_code=_code(), name="Test Subdivision", location="Test Location"
        ),
    )


def create_position(db: Session) -> m.Position:
    return create_obj(
        session=db,
        model=m.Position,
        data=s.PositionCreate(code=_code(), title="Engineer"),
    )


def create_project_type(db: Session) -> m.ProjectType:
    return create_obj(
        session=db,
        model=m.ProjectType,
        data=s.ProjectTypeCreate(code=_code(), name="Test Type"),
    )


def create_project(db: Session, subdivision_id: uuid.UUID) -> m.Project:
    return create_obj(
        session=db,
        model=m.Project,
        data=s.ProjectCreate(code=_code(), name="Test Project", subdivision_id=subdivision_id),
    )


def create_phase(db: Session, subdivision_id: uuid.UUID) -> m.Phase:
    return create_obj(
        session=db,
        model=m.Phase,
        data=s.PhaseCreate(code=_code(), name="Test Phase", subdivision_id=subdivision_id),
    )


def create_block(db: Session, phase_id: uuid.UUID) -> m.Blocks:
    return create_obj(
        session=db,
        model=m.Blocks,
        data=s.BlocksCreate(block_name="Block A", phase_id=phase_id),
    )


def create_lot(db: Session, blocks_id: uuid.UUID) -> m.Lots:
    return create_obj(
        session=db,
        model=m.Lots,
        data=s.LotsCreate(lot_num=1, lot_name="Lot 1", blocks_id=blocks_id),
    )


def create_owner(db: Session) -> m.Owner:
    return create_obj(
        session=db,
        model=m.Owner,
        data=s.OwnerCreate(first_name="Juan", last_name="Dela Cruz"),
    )


def create_category(
    db: Session,
    *,
    project_id: uuid.UUID,
    phase_id: uuid.UUID,
    blocks_id: uuid.UUID,
    owner_id: uuid.UUID | None,
    lot_id: uuid.UUID,
) -> m.Category:
    return create_obj(
        session=db,
        model=m.Category,
        data=s.CategoryCreate(
            code=_code(),
            description="House & Lot",
            project_id=project_id,
            phase_id=phase_id,
            blocks_id=blocks_id,
            owner_id=owner_id,
            lot_id=lot_id,
        ),
    )


def create_employee(db: Session, *, user_id: uuid.UUID | None = None) -> m.EmployeeRecords:
    return create_obj(
        session=db,
        model=m.EmployeeRecords,
        data=s.EmployeeRecordsCreate(
            employee_code=_code(),
            first_name="Test",
            last_name="Employee",
            birthdate="1990-01-01",
            user_id=user_id,
        ),
    )


def build_construction_chain(
    db: Session,
) -> dict:
    """Build the full Subdivision->Phase->Block->Lot / Project / Owner chain.

    Returns the created objects keyed by name for use in Category-related tests.
    """
    subdivision = create_subdivision(db)
    project = create_project(db, subdivision.id)
    phase = create_phase(db, subdivision.id)
    block = create_block(db, phase.id)
    lot = create_lot(db, block.id)
    owner = create_owner(db)
    category = create_category(
        db,
        project_id=project.id,
        phase_id=phase.id,
        blocks_id=block.id,
        owner_id=owner.id,
        lot_id=lot.id,
    )
    return {
        "subdivision": subdivision,
        "project": project,
        "phase": phase,
        "block": block,
        "lot": lot,
        "owner": owner,
        "category": category,
    }
