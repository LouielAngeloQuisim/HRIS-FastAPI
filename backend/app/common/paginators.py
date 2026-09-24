from collections.abc import Sequence
from typing import Generic, TypeVar

from pydantic import BaseModel
from sqlmodel import Session, func, select
from sqlmodel.sql.expression import Select

T = TypeVar("T")


class PaginationParams(BaseModel):
    skip: int = 0
    limit: int = 100

    def apply(self, statement: Select[T]) -> Select[T]:
        return statement.offset(self.skip).limit(self.limit)


class PaginatedResponse(BaseModel, Generic[T]):
    data: Sequence[T]
    count: int


def paginate(
    session: Session,
    statement: Select[T],
    params: PaginationParams,
) -> PaginatedResponse[T]:
    count_statement = select(func.count()).select_from(statement.subquery())
    count = session.exec(count_statement).one()

    items = session.exec(params.apply(statement)).all()

    return PaginatedResponse(data=items, count=count)
