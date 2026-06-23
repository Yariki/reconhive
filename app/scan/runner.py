"""Scan job runner: drives a ScanJob to completion and persists results.

Flow
----
1. Load the job, flip it to ``running``.
2. Load a fresh ``ScopeGuard`` for the engagement (the source of truth).
3. Expand the job's ``authorized_targets`` into individual host IPs.
4. Scan each host with the gate-enforcing scanner (bounded by an outer
   per-host semaphore so we don't expand a /16 into 65k coroutines at once).
5. Upsert ``hosts`` and their open ``services`` (PostgreSQL ON CONFLICT).
6. Record stats, audit ``job_started`` / ``job_finished``, set terminal status.

Out-of-scope hosts can't occur here (targets were filtered at plan time), but
if one somehow did, the scanner raises ``OutOfScopeError`` and that host is
recorded as an error rather than scanned.
"""
from __future__ import annotations

import asyncio
import ipaddress
import uuid
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import (
    AuditAction,
    AuditLog,
    Host,
    JobStatus,
    ScanJob,
    Service,
    Transport,
)
from ..scope.service import ScopeService
from ..fingerprint import Fingerprint, default_engine, fingerprint_service
from ..enrich import Enricher, HostEnrichment
from .ports import resolve_ports
from .progress import ScanProgress
from .scanner import HostResult, PortResult, TcpConnectScanner
from .text import sanitize_json, sanitize_text


def expand_targets(cidrs: list[str]) -> list[str]:
    """Expand CIDR strings into individual host IPs (excludes net/broadcast)."""
    out: list[str] = []
    for c in cidrs:
        net = ipaddress.ip_network(c, strict=False)
        if net.num_addresses == 1:
            out.append(str(net.network_address))
        else:
            out.extend(str(h) for h in net.hosts())
    return out


class ScanRunner:
    def __init__(
        self,
        session: AsyncSession,
        *,
        host_concurrency: int = 64,
        scanner_kwargs: dict | None = None,
        fingerprint: bool = True,
        http_probe: bool = True,
        enricher: Enricher | None = None,
        status_callback: Callable[[ScanJob], Awaitable[None]] | None = None,
    ) -> None:
        self._session = session
        self._host_sem = asyncio.Semaphore(host_concurrency)
        self._scanner_kwargs = scanner_kwargs or {}
        self._fingerprint = fingerprint
        self._http_probe = http_probe
        self._enricher = enricher if enricher is not None else Enricher()
        self._status_callback = status_callback

    async def _commit_and_notify(self, job: ScanJob) -> None:
        """Commit a lifecycle transition before publishing it to observers."""
        await self._session.commit()
        await self._session.refresh(job)
        if self._status_callback is not None:
            try:
                await self._status_callback(job)
            except Exception:
                # A disconnected WebSocket must never change a scan outcome.
                pass

    async def run_job(self, job_id: uuid.UUID) -> ScanJob:
        progress: ScanProgress | None = None
        job = await self._session.get(ScanJob, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")
        if job.status == JobStatus.pending:
            job.status = JobStatus.running
            job.started_at = datetime.now(timezone.utc)
            self._session.add(
                AuditLog(engagement_id=job.engagement_id, job_id=job.id,
                         actor=job.requested_by, action=AuditAction.job_started,
                         detail={"authorized": job.authorized_targets})
            )
            await self._commit_and_notify(job)
        elif job.status != JobStatus.running:
            raise ValueError(
                f"job {job_id} is {job.status}, expected pending or running"
            )

        try:
            guard = await ScopeService(self._session).load_guard(job.engagement_id)
            scanner = TcpConnectScanner(guard, **self._scanner_kwargs)
            ports = resolve_ports(job.params)
            ips = expand_targets(job.authorized_targets)

            progress = ScanProgress(ips, ports, job.stats)
            progress.phase = "scanning"
            job.stats = progress.snapshot()
            await self._commit_and_notify(job)

            loop = asyncio.get_running_loop()
            last_progress_emit = loop.time()
            events: asyncio.Queue = asyncio.Queue(maxsize=2_000)

            async def on_port_result(ip: str, result: PortResult) -> None:
                await events.put(("port", ip, result))

            async def scan_target(ip: str) -> None:
                try:
                    result = await self._scan_one(
                        scanner, ip, ports, on_port_result
                    )
                except Exception as exc:  # reported by the coordinator
                    await events.put(("error", ip, exc))
                else:
                    await events.put(("host", ip, result))

            scan_tasks = [asyncio.create_task(scan_target(ip)) for ip in ips]
            hosts_finished = 0
            try:
                while hosts_finished < len(ips):
                    event, ip, payload = await events.get()
                    if event == "port":
                        progress.record_port(ip, payload)
                        if progress.ports_scanned == progress.ports_total:
                            progress.phase = "analyzing"
                    else:
                        hosts_finished += 1
                        if event == "error":
                            progress.record_scan_error(ip)
                        else:
                            result = payload
                            fps = await self._fingerprint_host(result)
                            host_enr, tls_map = await self._enrich_host(result, fps)
                            await self._persist(
                                job.engagement_id, result, fps, host_enr, tls_map
                            )
                            progress.record_host_result(
                                result.ip,
                                result.alive,
                                result.open_ports,
                                fps,
                                host_enr,
                                tls_map,
                            )

                    now = loop.time()
                    has_new_service = event == "host" and bool(payload.open_ports)
                    if (
                        now - last_progress_emit >= 0.5
                        or has_new_service
                        or hosts_finished == len(ips)
                    ):
                        job.stats = progress.snapshot()
                        await self._commit_and_notify(job)
                        last_progress_emit = now
            except Exception:
                for task in scan_tasks:
                    task.cancel()
                await asyncio.gather(*scan_tasks, return_exceptions=True)
                raise
            else:
                await asyncio.gather(*scan_tasks)

            if progress.phase != "analyzing":
                progress.phase = "analyzing"
                if progress.ports_scanned or progress.errors:
                    job.stats = progress.snapshot()
                    await self._commit_and_notify(job)

            job.status = JobStatus.completed
            progress.phase = "completed"
            job.stats = progress.snapshot()
        except Exception as exc:  # noqa: BLE001
            await self._session.rollback()
            job = await self._session.get(ScanJob, job_id, populate_existing=True)
            if job is not None:
                job.status = JobStatus.failed
                job.error = str(exc)
                job.finished_at = datetime.now(timezone.utc)
                job.stats = {**(job.stats or {}), "phase": "failed"}
                self._session.add(
                    AuditLog(engagement_id=job.engagement_id, job_id=job.id,
                             actor=job.requested_by,
                             action=AuditAction.job_finished,
                             verdict="failed", reason=str(exc))
                )
                await self._commit_and_notify(job)
            raise

        job.finished_at = datetime.now(timezone.utc)
        self._session.add(
            AuditLog(engagement_id=job.engagement_id, job_id=job.id,
                     actor=job.requested_by, action=AuditAction.job_finished,
                     verdict="completed", reason="scan complete",
                     detail=job.stats)
        )
        await self._commit_and_notify(job)
        return job

    async def _scan_one(
        self,
        scanner: TcpConnectScanner,
        ip: str,
        ports: list[int],
        on_port_result: Callable[[str, PortResult], Awaitable[None]] | None = None,
    ) -> HostResult:
        async with self._host_sem:
            return await scanner.scan_host(ip, ports, on_port_result)

    async def _fingerprint_host(self, result: HostResult) -> dict[int, Fingerprint]:
        """Fingerprint every open port on a host concurrently."""
        if not self._fingerprint:
            return {}
        open_ports = result.open_ports
        fps = await asyncio.gather(
            *(
                fingerprint_service(
                    result.ip, p.port, p.banner,
                    engine=default_engine,
                    http_probe_enabled=self._http_probe,
                )
                for p in open_ports
            )
        )
        return {p.port: fp for p, fp in zip(open_ports, fps)}

    async def _enrich_host(
        self, result: HostResult, fps: dict[int, Fingerprint]
    ) -> tuple[HostEnrichment, dict[int, dict]]:
        """Host-level geo/tags (sync) + per-service TLS certs (async)."""
        host_enr = self._enricher.enrich_host(result.ip)

        tls_ports = [
            p.port for p in result.open_ports
            if self._enricher.is_tls_port(
                p.port, fps.get(p.port).service if fps.get(p.port) else None
            )
        ]
        tls_results = await asyncio.gather(
            *(self._enricher.enrich_service_tls(result.ip, port) for port in tls_ports)
        )
        tls_map = {
            port: cert for port, cert in zip(tls_ports, tls_results) if cert is not None
        }
        return host_enr, tls_map

    async def _persist(
        self,
        engagement_id: uuid.UUID,
        result: HostResult,
        fingerprints: dict[int, Fingerprint] | None = None,
        host_enr: HostEnrichment | None = None,
        tls_map: dict[int, dict] | None = None,
    ) -> int:
        """Upsert host + its open services. Returns count of open services."""
        now = datetime.now(timezone.utc)
        fingerprints = fingerprints or {}
        tls_map = tls_map or {}

        host_vals = {"engagement_id": engagement_id, "ip": result.ip, "last_seen": now}
        host_set: dict = {"last_seen": now}
        if host_enr is not None:
            for fld in ("country", "city", "latitude", "longitude", "asn", "as_org"):
                val = getattr(host_enr, fld)
                if val is not None:
                    host_vals[fld] = val
                    host_set[fld] = val
            if host_enr.tags:
                host_vals["tags"] = host_enr.tags
                host_set["tags"] = host_enr.tags
        # also adopt an OS hint from any fingerprint
        os_guess = next((fp.os for fp in fingerprints.values() if fp and fp.os), None)
        if os_guess:
            host_vals["os_guess"] = os_guess
            host_set["os_guess"] = os_guess

        host_stmt = (
            pg_insert(Host)
            .values(**host_vals)
            .on_conflict_do_update(index_elements=["engagement_id", "ip"], set_=host_set)
            .returning(Host.id)
        )
        host_id = (await self._session.execute(host_stmt)).scalar_one()

        open_ports = result.open_ports
        for p in open_ports:
            fp = fingerprints.get(p.port)
            product = sanitize_text(fp.product) if fp else None
            version = sanitize_text(fp.version) if fp else None
            extra_info = sanitize_text(fp.extra_info) if fp else None
            cpe = [sanitize_text(value) for value in fp.cpe] if fp else []
            banner = sanitize_text(p.banner)
            tls = sanitize_json(tls_map.get(p.port))
            data = {"latency_ms": p.latency_ms} if p.latency_ms else {}
            if fp is not None:
                data["fingerprint"] = {
                    "service": sanitize_text(fp.service),
                    "confidence": fp.confidence,
                    "source": sanitize_text(fp.source),
                    "os": sanitize_text(fp.os),
                }
            data = sanitize_json(data)
            search_text = " ".join(filter(None, [product, version, banner]))
            svc_stmt = (
                pg_insert(Service)
                .values(
                    host_id=host_id,
                    port=p.port,
                    transport=Transport.tcp,
                    product=product,
                    version=version,
                    extra_info=extra_info,
                    cpe=cpe,
                    banner=banner,
                    tls=tls,
                    data=data,
                    last_seen=now,
                    search_vector=func.to_tsvector(
                        "english", search_text,
                    ),
                )
                .on_conflict_do_update(
                    index_elements=["host_id", "port", "transport"],
                    set_={
                        "product": product,
                        "version": version,
                        "extra_info": extra_info,
                        "cpe": cpe,
                        "banner": banner,
                        "tls": tls,
                        "data": data,
                        "last_seen": now,
                        "search_vector": func.to_tsvector(
                            "english", search_text,
                        ),
                    },
                )
            )
            await self._session.execute(svc_stmt)
        return len(open_ports)
