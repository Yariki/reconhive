"""FastAPI dependencies."""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Engagement
from ..db.session import SessionFactory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_engagement(
    engagement_id: uuid.UUID = Path(...),
    session: AsyncSession = Depends(get_session),
) -> Engagement:
    eng = await session.get(Engagement, engagement_id)
    if eng is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "engagement not found")
    return eng
