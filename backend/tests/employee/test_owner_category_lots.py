"""Phase 1 test set C — Owner/Category/Lots relationship contract (design §5 Point 3).

The authoritative ownership link is Owner -> Category -> Lots. Owner has NO
lot_id/block_id FK fields; it only carries denormalised lot_no/block strings.
These tests pin that shape and fail loudly if the FKs are re-added.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.employee import models as m
from tests.utils.employee import build_construction_chain

API = settings.API_V1_STR


class TestOwnerCategoryLotsContract:
    def test_owner_model_has_no_lot_id_or_block_id(self) -> None:
        """C.2 regression: Owner must NOT expose lot_id/block_id FKs."""
        fields = set(m.Owner.model_fields.keys())
        assert "lot_id" not in fields
        assert "block_id" not in fields
        # It must retain the denormalised string labels instead.
        assert "lot_no" in fields
        assert "block" in fields

    def test_owner_public_schema_has_no_lot_id_or_block_id(self) -> None:
        from app.employee import schemas as s

        fields = set(s.OwnerPublic.model_fields.keys())
        assert "lot_id" not in fields
        assert "block_id" not in fields

    def test_ownership_resolves_through_category(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        """C.1: 'who owns Lot X' is answered via Category, not Owner."""
        chain = build_construction_chain(db)
        owner = chain["owner"]
        lot = chain["lot"]

        from sqlmodel import select

        category = db.exec(
            select(m.Category).where(m.Category.lot_id == lot.id)
        ).first()
        assert category is not None
        assert category.owner_id == owner.id

        # Expose via the endpoint that reads the owner's lot through Category.
        r = client.get(
            f"{API}/owners/{owner.id}/lot", headers=superuser_token_headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["id"] == str(category.id)

    def test_owner_display_labels_need_not_match_category(
        self, db: Session
    ) -> None:
        """C.3: Owner.lot_no/block are non-authoritative labels; they may differ
        from the Category's actual linked Lot/Block without error."""
        chain = build_construction_chain(db)
        owner = chain["owner"]
        category = chain["category"]

        # Set owner display labels that disagree with the linked category.
        owner.lot_no = "DIFFERENT-LOT"
        owner.block = "DIFFERENT-BLOCK"
        db.add(owner)
        db.commit()

        db.refresh(owner)
        assert owner.lot_no == "DIFFERENT-LOT"
        # Category still links the real lot independently; no integrity error raised.
        assert category.lot_id is not None
