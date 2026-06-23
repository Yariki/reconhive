"""Engagement + scope management."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import Engagement, ScopeEntryRow
from ..deps import get_engagement, get_session
from ..schemas import (
    EngagementCreate, EngagementOut, ScopeEntryCreate, ScopeEntryOut,
)

router = APIRouter(prefix="/engagements", tags=["engagements"])


@router.post("", response_model=EngagementOut, status_code=status.HTTP_201_CREATED)
async def create_engagement(body: EngagementCreate,
                            session: AsyncSession = Depends(get_session)):
    if body.ends_at <= body.starts_at:
        raise HTTPException(422,
                            "ends_at must be after starts_at")
    eng = Engagement(**body.model_dump())
    session.add(eng)
    await session.flush()
    return eng


@router.get("", response_model=list[EngagementOut])
async def list_engagements(session: AsyncSession = Depends(get_session)):
    rows = await session.scalars(select(Engagement).order_by(Engagement.created_at.desc()))
    return list(rows)


@router.get("/{engagement_id}", response_model=EngagementOut)
async def get_one(eng: Engagement = Depends(get_engagement)):
    return eng


@router.post("/{engagement_id}/scope", response_model=ScopeEntryOut,
             status_code=status.HTTP_201_CREATED)
async def add_scope(body: ScopeEntryCreate,
                    eng: Engagement = Depends(get_engagement),
                    session: AsyncSession = Depends(get_session)):
    entry = ScopeEntryRow(engagement_id=eng.id, **body.model_dump())
    session.add(entry)
    await session.flush()
    return entry


@router.get("/{engagement_id}/scope", response_model=list[ScopeEntryOut])
async def list_scope(eng: Engagement = Depends(get_engagement),
                     session: AsyncSession = Depends(get_session)):
    rows = await session.scalars(
        select(ScopeEntryRow).where(ScopeEntryRow.engagement_id == eng.id)
    )
    return list(rows)
