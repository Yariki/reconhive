"""Scan job lifecycle: plan, list, get, run."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import AuditAction, AuditLog, Engagement, JobStatus, ScanJob
from ...db.session import SessionFactory
from ...scan.runner import ScanRunner
from ...scope.exceptions import OutOfScopeError, ScopeError
from ...scope.service import EngagementInactiveError, JobTooLargeError, ScopeService
from ..deps import get_engagement, get_session
from ..job_events import job_event_hub, job_payload
from ..schemas import ScanJobCreate, ScanJobOut

router = APIRouter(tags=["jobs"])


@router.post("/engagements/{engagement_id}/jobs", response_model=ScanJobOut,
             status_code=status.HTTP_201_CREATED)
async def plan_job(body: ScanJobCreate,
                   eng: Engagement = Depends(get_engagement),
                   session: AsyncSession = Depends(get_session)):
    params = {"ports": body.ports} if body.ports else {}
    try:
        job = await ScopeService(session).plan_job(
            eng.id, body.job_type, body.targets,
            requested_by=body.requested_by, params=params,
        )
    except (OutOfScopeError,) as exc:
        raise HTTPException(422, str(exc)) from exc
    except JobTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc
    except EngagementInactiveError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ScopeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await session.commit()
    await session.refresh(job)
    await job_event_hub.publish_job(job)
    return job


@router.get("/engagements/{engagement_id}/jobs", response_model=list[ScanJobOut])
async def list_jobs(eng: Engagement = Depends(get_engagement),
                    session: AsyncSession = Depends(get_session)):
    rows = await session.scalars(
        select(ScanJob).where(ScanJob.engagement_id == eng.id)
        .order_by(ScanJob.created_at.desc())
    )
    return list(rows)


@router.get("/jobs/{job_id}", response_model=ScanJobOut)
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    job = await session.get(ScanJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return job


@router.websocket("/ws/engagements/{engagement_id}/jobs")
async def job_updates(websocket: WebSocket, engagement_id: uuid.UUID):
    """Stream full job snapshots for one engagement."""
    async with SessionFactory() as session:
        engagement = await session.get(Engagement, engagement_id)
        if engagement is None:
            await websocket.close(code=4404, reason="engagement not found")
            return

    await job_event_hub.connect(engagement_id, websocket)
    try:
        # Register before taking the snapshot. The updated_at field lets the
        # client ignore an older snapshot if an event arrives concurrently.
        async with SessionFactory() as session:
            rows = await session.scalars(
                select(ScanJob)
                .where(ScanJob.engagement_id == engagement_id)
                .order_by(ScanJob.created_at.desc())
            )
            await websocket.send_json({
                "type": "jobs.snapshot",
                "jobs": [job_payload(job) for job in rows],
            })

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        job_event_hub.disconnect(engagement_id, websocket)


async def _claim_job(job_id: uuid.UUID, session: AsyncSession) -> ScanJob:
    """Atomically claim a pending job and expose the running state."""
    stmt = (
        update(ScanJob)
        .where(ScanJob.id == job_id, ScanJob.status == JobStatus.pending)
        .values(status=JobStatus.running, started_at=datetime.now(timezone.utc))
        .returning(ScanJob)
    )
    job = (await session.execute(stmt)).scalar_one_or_none()
    if job is None:
        existing = await session.get(ScanJob, job_id)
        if existing is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"job is {existing.status.value}, not pending",
        )

    session.add(
        AuditLog(
            engagement_id=job.engagement_id,
            job_id=job.id,
            actor=job.requested_by,
            action=AuditAction.job_started,
            detail={"authorized": job.authorized_targets},
        )
    )
    await session.commit()
    await session.refresh(job)
    await job_event_hub.publish_job(job)
    return job


async def _run_in_background(job_id: uuid.UUID) -> None:
    """Run a job in its own session (used by BackgroundTasks)."""
    async with SessionFactory() as session:
        try:
            await ScanRunner(
                session, status_callback=job_event_hub.publish_job
            ).run_job(job_id)
        except Exception:
            await session.rollback()


@router.post("/jobs/{job_id}/run", response_model=ScanJobOut)
async def run_job(job_id: uuid.UUID, background: BackgroundTasks,
                  wait: bool = False, session: AsyncSession = Depends(get_session)):
    """Execute a pending job. ``wait=true`` runs inline (handy for small jobs
    and tests); otherwise it's scheduled as a background task and returns
    immediately with the job in its current state."""
    job = await _claim_job(job_id, session)
    if wait:
        try:
            return await ScanRunner(
                session, status_callback=job_event_hub.publish_job
            ).run_job(job_id)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "job execution failed"
            ) from exc
    background.add_task(_run_in_background, job_id)
    return job
