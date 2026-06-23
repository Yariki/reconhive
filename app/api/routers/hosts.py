"""Host listing and detail."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...db.models import Engagement, Host
from ..deps import get_engagement, get_session
from ..schemas import HostOut, HostSummary

router = APIRouter(tags=["hosts"])


@router.get("/engagements/{engagement_id}/hosts", response_model=list[HostSummary])
async def list_hosts(eng: Engagement = Depends(get_engagement),
                     session: AsyncSession = Depends(get_session),
                     limit: int = 100, offset: int = 0):
    rows = await session.scalars(
        select(Host).where(Host.engagement_id == eng.id)
        .order_by(Host.last_seen.desc()).limit(limit).offset(offset)
    )
    return list(rows)


@router.get("/hosts/{host_id}", response_model=HostOut)
async def get_host(host_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    host = await session.scalar(
        select(Host).where(Host.id == host_id).options(selectinload(Host.services))
    )
    if host is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "host not found")
    return host
