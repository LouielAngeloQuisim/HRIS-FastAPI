"""Pagination parameter parsing and helpers."""

from math import ceil

from fastapi import Query

from .responses import Meta


def pagination_params(
    *,
    skip: int = Query(default=0, ge=0, description="Rows to skip"),
    limit: int = Query(default=20, ge=1, le=200, description="Max rows to return"),
) -> dict[str, int]:
    return {"skip": skip, "limit": limit}


def make_meta(*, total: int, skip: int, limit: int, count: int) -> Meta:
    return Meta.build(total=total, skip=skip, limit=limit, count=count)


def total_pages(total: int, limit: int) -> int:
    if limit <= 0 or total <= 0:
        return 0
    return ceil(total / limit)
