"""Bridge between persisted scope and the in-memory ScopeGuard.

This is the layer the API and workers call. Responsibilities:

* build a :class:`ScopeGuard` snapshot for an engagement from the DB
* record every authorization decision into ``audit_log``
* plan a scan job: run the requested targets through the guard, persist the
  authorized / rejected partition, enforce the per-job host cap, and emit audit
  events -- all in one transaction

Decisions are still made by the pure ``ScopeGuard``; this only adds I/O.
"""
from __future__ import annotations

import ipaddress
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.models import (
    AuditAction,
    AuditLog,
    Engagement,
    JobStatus,
    JobType,
    ScanJob,
    ScopeEntryRow,
    ScopeKind,
)
from .exceptions import OutOfScopeError, ScopeError
from .guard import EntryKind, ScopeEntry, ScopeGuard, ScopeResult, parse_target


class EngagementInactiveError(ScopeError):
    """Engagement is disabled or outside its authorization window."""


class JobTooLargeError(ScopeError):
    """Authorized host count exceeds the configured per-job cap."""


def _to_guard_entry(row: ScopeEntryRow) -> ScopeEntry:
    return ScopeEntry(
        cidr=ipaddress.ip_network(row.cidr, strict=False),
        kind=EntryKind(row.kind.value),
        engagement_id=str(row.engagement_id),
        note=row.note or "",
        expires_at=row.expires_at,
    )


class ScopeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    # -- loading -----------------------------------------------------------

    async def load_guard(
        self, engagement_id: uuid.UUID, *, now: datetime | None = None
    ) -> ScopeGuard:
        now = now or datetime.now(timezone.utc)

        engagement = await self._session.get(Engagement, engagement_id)
        if engagement is None:
            raise ScopeError(f"engagement {engagement_id} not found")
        if not engagement.is_active:
            raise EngagementInactiveError(f"engagement {engagement_id} is inactive")
        if not (engagement.starts_at <= now <= engagement.ends_at):
            raise EngagementInactiveError(
                f"engagement {engagement_id} outside authorization window "
                f"({engagement.starts_at} .. {engagement.ends_at})"
            )

        rows = (
            await self._session.scalars(
                select(ScopeEntryRow).where(
                    ScopeEntryRow.engagement_id == engagement_id
                )
            )
        ).all()
        # The engagement window itself caps every entry's effective expiry.
        entries = []
        for row in rows:
            e = _to_guard_entry(row)
            eff_expiry = engagement.ends_at
            if e.expires_at is not None:
                eff_expiry = min(eff_expiry, e.expires_at)
            entries.append(
                ScopeEntry(e.cidr, e.kind, e.engagement_id, e.note, eff_expiry)
            )
        return ScopeGuard.from_entries(entries, now=now)

    # -- audited single-host gate -----------------------------------------

    async def authorize_host(
        self,
        engagement_id: uuid.UUID,
        host: str,
        *,
        actor: str,
        job_id: uuid.UUID | None = None,
        guard: ScopeGuard | None = None,
    ) -> None:
        """Hard gate with audit. Raises :class:`OutOfScopeError` if denied.

        Pass a pre-loaded ``guard`` in hot loops to avoid re-querying per host;
        the audit row is still written for every decision.
        """
        guard = guard or await self.load_guard(engagement_id)
        decision = guard.evaluate(host)

        self._session.add(
            AuditLog(
                engagement_id=engagement_id,
                job_id=job_id,
                actor=actor,
                action=AuditAction.scope_decision,
                target=host,
                verdict=decision.verdict.value,
                reason=decision.reason,
                detail={"matched": str(decision.matched_entry.cidr)
                        if decision.matched_entry else None},
            )
        )
        if not decision.authorized:
            # Persist the audit row even though we raise; flush within the
            # caller's transaction so the denial is recorded.
            await self._session.flush()
            raise OutOfScopeError(host, decision.reason)

    # -- audited job planner ----------------------------------------------

    async def plan_job(
        self,
        engagement_id: uuid.UUID,
        job_type: JobType,
        requested_targets: list[str],
        *,
        requested_by: str,
        params: dict | None = None,
    ) -> ScanJob:
        """Validate targets against scope, persist a ScanJob, audit it.

        The job is created in ``pending`` only if there is at least one
        authorized network and the host count is within the cap. Rejected
        portions are stored on the job for transparency.
        """
        guard = await self.load_guard(engagement_id)
        result: ScopeResult = guard.filter_targets(requested_targets)

        host_count = result.authorized_host_count()
        if host_count > self._settings.max_authorized_hosts_per_job:
            self._session.add(
                AuditLog(
                    engagement_id=engagement_id,
                    actor=requested_by,
                    action=AuditAction.job_submitted,
                    verdict="rejected",
                    reason=(f"authorized host count {host_count} exceeds cap "
                            f"{self._settings.max_authorized_hosts_per_job}"),
                    detail={"requested": requested_targets},
                )
            )
            await self._session.flush()
            raise JobTooLargeError(
                f"{host_count} authorized hosts exceeds per-job cap "
                f"{self._settings.max_authorized_hosts_per_job}"
            )

        if not result.authorized:
            self._session.add(
                AuditLog(
                    engagement_id=engagement_id,
                    actor=requested_by,
                    action=AuditAction.job_submitted,
                    verdict="rejected",
                    reason="no requested target is in scope",
                    detail={"requested": requested_targets,
                            "rejected": [str(n) for n in result.rejected]},
                )
            )
            await self._session.flush()
            raise OutOfScopeError(
                ", ".join(requested_targets), "no requested target is in scope"
            )

        job = ScanJob(
            engagement_id=engagement_id,
            job_type=job_type,
            status=JobStatus.pending,
            requested_targets=requested_targets,
            authorized_targets=[str(n) for n in result.authorized],
            rejected_targets=[str(n) for n in result.rejected],
            requested_by=requested_by,
            params=params or {},
            stats={"authorized_hosts": host_count,
                   "authorized_blocks": len(result.authorized),
                   "rejected_blocks": len(result.rejected)},
        )
        self._session.add(job)
        await self._session.flush()  # populate job.id

        self._session.add(
            AuditLog(
                engagement_id=engagement_id,
                job_id=job.id,
                actor=requested_by,
                action=AuditAction.job_submitted,
                verdict="authorized" if result.fully_authorized else "partial",
                reason=f"queued {host_count} authorized hosts",
                detail={"authorized": job.authorized_targets,
                        "rejected": job.rejected_targets},
            )
        )
        return job
