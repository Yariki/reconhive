"""Search DSL endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import Engagement
from ...search import search as run_search
from ...search.exceptions import SearchSyntaxError
from ..deps import get_engagement, get_session
from ..schemas import SearchResult

router = APIRouter(tags=["search"])


@router.get("/engagements/{engagement_id}/search", response_model=list[SearchResult])
async def search_endpoint(
    q: str = Query("", description='DSL query, e.g. port:443 product:nginx country:UA'),
    limit: int = Query(50, le=500),
    offset: int = 0,
    eng: Engagement = Depends(get_engagement),
    session: AsyncSession = Depends(get_session),
):
    try:
        services = await run_search(session, eng.id, q, limit=limit, offset=offset)
    except SearchSyntaxError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return [SearchResult(host=s.host, service=s) for s in services]
