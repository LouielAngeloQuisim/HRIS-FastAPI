"""Phase 1 test set A2 — Blocks/Lots DELETE endpoints + soft-deleted-Category guard.

Covers design §5 Point 1 & 2:
- Permission gate on DELETE /blocks/{id} and DELETE /lots/{id}.
- Baseline: zero references -> delete succeeds.
- Soft-deleted-Category exception: deleting a Block/Lot referenced only by a
  soft-deleted Category must succeed (the guard counts only ACTIVE Categories).
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.config.settings import settings
from app.employee.models import Blocks, Category, Lots
from tests.utils.employee import (
    build_construction_chain,
    create_block,
)

API = settings.API_V1_STR


@pytest.fixture
def block_lot_chain(db: Session):
    """A construction chain plus a dedicated Block/Lot pair for delete tests."""
    chain = build_construction_chain(db)
    yield chain
    db.execute(delete(Category))
    db.execute(delete(Lots))
    db.execute(delete(Blocks))
    db.commit()


class TestBlocksLotsDelete:
    def test_delete_requires_projects_delete_permission(
        self, client: TestClient, normal_user_token_headers
    ) -> None:
        """A user without projects/delete gets 403 on the DELETE endpoint."""
        r = client.delete(
            f"{API}/blocks/00000000-0000-0000-0000-000000000000",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403
        r = client.delete(
            f"{API}/lots/00000000-0000-0000-0000-000000000000",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403

    def test_baseline_zero_references_deletes(
        self, client: TestClient, superuser_token_headers, block_lot_chain, db: Session
    ) -> None:
        """A Block referenced by NO category deletes immediately (200/204)."""
        phase = block_lot_chain["phase"]
        orphan_block = create_block(db, phase.id)
        r = client.delete(
            f"{API}/blocks/{orphan_block.id}", headers=superuser_token_headers
        )
        assert r.status_code == 200, r.text
        db.refresh(orphan_block)
        assert orphan_block.is_deleted is True

    def test_active_category_blocks_then_soft_deleted_category_allows(
        self, client: TestClient, superuser_token_headers, block_lot_chain, db: Session
    ) -> None:
        """Point 1 core: 409 while an ACTIVE category references it, then 200 after
        that category is soft-deleted. Proves the guard excludes soft-deleted rows."""
        block = block_lot_chain["block"]
        lot = block_lot_chain["lot"]
        category = block_lot_chain["category"]

        # 1. Active category references block & lot -> 409
        r = client.delete(f"{API}/blocks/{block.id}", headers=superuser_token_headers)
        assert r.status_code == 409, r.text
        r = client.delete(f"{API}/lots/{lot.id}", headers=superuser_token_headers)
        assert r.status_code == 409, r.text

        # 2. Soft-delete the category (is_deleted = true)
        r = client.delete(
            f"{API}/categories/{category.id}", headers=superuser_token_headers
        )
        assert r.status_code == 200, r.text
        db.refresh(category)
        assert category.is_deleted is True

        # 3. Now the same block & lot are deletable (only soft-deleted refs remain)
        r = client.delete(f"{API}/blocks/{block.id}", headers=superuser_token_headers)
        assert r.status_code == 200, r.text
        db.refresh(block)
        assert block.is_deleted is True
        assert block.deleted_at is not None

        r = client.delete(f"{API}/lots/{lot.id}", headers=superuser_token_headers)
        assert r.status_code == 200, r.text
        db.refresh(lot)
        assert lot.is_deleted is True
        assert lot.deleted_at is not None

    def test_guard_counts_only_active_categories(
        self, db: Session, block_lot_chain
    ) -> None:
        """Service-level proof the guard predicate is is_deleted = false only."""
        from app.employee.selectors import count_active_categories_referencing

        category = block_lot_chain["category"]
        block = block_lot_chain["block"]
        lot = block_lot_chain["lot"]

        assert count_active_categories_referencing(session=db, blocks_id=block.id) == 1
        assert count_active_categories_referencing(session=db, lot_id=lot.id) == 1

        # Soft-delete the category; the count drops to zero (soft-deleted excluded).
        category.is_deleted = True
        db.add(category)
        db.commit()
        assert count_active_categories_referencing(session=db, blocks_id=block.id) == 0
        assert count_active_categories_referencing(session=db, lot_id=lot.id) == 0
