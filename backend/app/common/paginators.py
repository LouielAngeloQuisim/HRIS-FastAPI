from collections.abc import Sequence
from typing import Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select as SASelect
from sqlmodel import Session, func, select

T = TypeVar("T")


class PaginationParams(BaseModel):
    skip: int = 0
    limit: int = 100

    def apply(self, statement: SASelect) -> SASelect:
        return statement.offset(self.skip).limit(self.limit)


class PaginatedResponse(BaseModel, Generic[T]):
    data: Sequence[T]
    count: int


def paginate(
    session: Session,
    statement: SASelect,
    params: PaginationParams,
) -> PaginatedResponse:
    count_statement = select(func.count()).select_from(statement.subquery())
    count = session.exec(count_statement).one()

    items = session.exec(params.apply(statement)).all()

    return PaginatedResponse(data=items, count=count)
