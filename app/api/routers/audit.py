"""Audit log access -- the engagement's compliance trail."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import AuditLog, Engagement
from ..deps import get_engagement, get_session
from ..schemas import AuditOut

router = APIRouter(tags=["audit"])


@router.get("/engagements/{engagement_id}/audit", response_model=list[AuditOut])
async def list_audit(eng: Engagement = Depends(get_engagement),
                     session: AsyncSession = Depends(get_session),
                     limit: int = 200):
    rows = await session.scalars(
        select(AuditLog).where(AuditLog.engagement_id == eng.id)
        .order_by(AuditLog.ts.desc()).limit(limit)
    )
    return list(rows)
