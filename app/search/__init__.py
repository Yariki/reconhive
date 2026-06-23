"""Search DSL: lexer -> parser -> compiler -> async search()."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Service
from .compiler import compile_query
from .exceptions import SearchError, SearchSyntaxError
from .parser import Query, parse

__all__ = ["search", "compile_query", "parse", "Query", "SearchError", "SearchSyntaxError"]


async def search(
    session: AsyncSession,
    engagement_id: uuid.UUID,
    query: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[Service]:
    """Run a DSL query, scoped to one engagement. Returns Service rows with
    their Host eager-loaded (one row per service)."""
    stmt = compile_query(query, engagement_id, limit=limit, offset=offset)
    result = await session.execute(stmt)
    return list(result.scalars().unique().all())
