import uuid
from typing import Any
from sqlmodel import Session, select, func

from app.item.models import Item


def get_items(
    *, session: Session, owner_id: uuid.UUID | None = None, skip: int = 0, limit: int = 100
) -> tuple[list[Item], int]:
    if owner_id:
        count_statement = (
            select(func.count())
            .select_from(Item)
            .where(Item.owner_id == owner_id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Item)
            .where(Item.owner_id == owner_id)
            .order_by(Item.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
    else:
        count_statement = select(func.count()).select_from(Item)
        count = session.exec(count_statement).one()
        statement = (
            select(Item)
            .order_by(Item.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
    items = session.exec(statement).all()
    return items, count


def get_item_by_id(*, session: Session, item_id: uuid.UUID) -> Item | None:
    return session.get(Item, item_id)