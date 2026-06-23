"""End-to-end integration tests against a real PostgreSQL.

Exercises the full vertical slice on real PG types (INET, CIDR, JSONB, ARRAY,
tsvector): scope planning, a live scan of localhost through the gate, fingerprint
+ enrichment persistence, and the search DSL.

Skipped automatically if no PostgreSQL is reachable at RECONHIVE_TEST_DSN
(default: the local dev DSN).
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import (
    Engagement, Host, JobStatus, JobType, ScanJob, ScopeEntryRow, ScopeKind,
    Service, Transport,
)
from app.scan.runner import ScanRunner
from app.scope.exceptions import OutOfScopeError
from app.scope.service import ScopeService
from app.search import search

DSN = os.environ.get(
    "RECONHIVE_TEST_DSN",
    "postgresql+asyncpg://reconhive:reconhive@127.0.0.1:5432/reconhive",
)
UTC = timezone.utc


def _pg_available() -> bool:
    import asyncpg
    sync_dsn = DSN.replace("+asyncpg", "")

    async def ping():
        try:
            c = await asyncpg.connect(sync_dsn, timeout=3)
            await c.close()
            return True
        except Exception:
            return False
    return asyncio.run(ping())


pytestmark = pytest.mark.skipif(not _pg_available(), reason="no PostgreSQL")


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(DSN)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await s.execute(text(
            "TRUNCATE audit_log, services, hosts, scan_jobs, scope_entries, "
            "engagements RESTART IDENTITY CASCADE"
        ))
        await s.commit()
        yield s
    await engine.dispose()


async def _make_engagement(s: AsyncSession, *, allow="127.0.0.0/8") -> uuid.UUID:
    now = datetime.now(UTC)
    eng = Engagement(
        client_name="Acme", authorization_ref="SOW-2026-001",
        starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=30),
        is_active=True,
    )
    s.add(eng)
    await s.flush()
    s.add(ScopeEntryRow(engagement_id=eng.id, cidr=allow, kind=ScopeKind.allow))
    await s.commit()
    return eng.id


# --- scope planning on real PG ---------------------------------------------

@pytest.mark.asyncio
async def test_plan_job_partitions_targets(session):
    eid = await _make_engagement(session)
    job = await ScopeService(session).plan_job(
        eid, JobType.port_scan, ["127.0.0.1/32", "8.8.8.8"],
        requested_by="tester",
    )
    await session.commit()
    assert job.authorized_targets == ["127.0.0.1/32"]
    assert job.rejected_targets == ["8.8.8.8/32"]

    rows = (await session.execute(text(
        "select action, verdict from audit_log order by id"
    ))).all()
    assert any(a == "job_submitted" for a, _ in rows)


@pytest.mark.asyncio
async def test_plan_job_rejects_out_of_scope(session):
    eid = await _make_engagement(session)
    with pytest.raises(OutOfScopeError):
        await ScopeService(session).plan_job(
            eid, JobType.port_scan, ["10.0.0.0/24"], requested_by="tester",
        )


# --- full scan of localhost through the gate -------------------------------

@pytest.mark.asyncio
async def test_scan_localhost_persists_fingerprint(session):
    eid = await _make_engagement(session)

    async def ssh(reader, writer):
        writer.write(b"SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13\r\n")
        await writer.drain()
        await asyncio.sleep(0.05)
        writer.close()

    server = await asyncio.start_server(ssh, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        job = await ScopeService(session).plan_job(
            eid, JobType.banner_grab, ["127.0.0.1/32"],
            requested_by="tester", params={"ports": [port]},
        )
        await session.commit()

        observed_updates = []

        async def observe_committed_status(updated_job):
            async with AsyncSession(bind=session.bind) as observer:
                committed = await observer.scalar(
                    select(ScanJob).where(ScanJob.id == updated_job.id)
                )
                observed_updates.append((committed.status, committed.stats.get("phase")))

        runner = ScanRunner(
            session,
            http_probe=False,
            status_callback=observe_committed_status,
        )
        await runner.run_job(job.id)
        await session.commit()
    finally:
        server.close()
        await server.wait_closed()

    svc = (await session.execute(text(
        "select product, version, h.ip::text, h.tags "
        "from services s join hosts h on h.id = s.host_id"
    ))).first()
    assert svc is not None
    assert svc[0] == "OpenSSH" and svc[1] == "9.6p1"
    assert svc[2].startswith("127.0.0.1")
    assert "loopback" in svc[3]  # netclass enrichment ran
    assert observed_updates[0][0] == JobStatus.running
    assert (JobStatus.running, "scanning") in observed_updates
    assert (JobStatus.running, "analyzing") in observed_updates
    assert observed_updates[-1] == (JobStatus.completed, "completed")


@pytest.mark.asyncio
async def test_failed_job_status_is_committed(session):
    eid = await _make_engagement(session)
    job = await ScopeService(session).plan_job(
        eid,
        JobType.port_scan,
        ["127.0.0.1/32"],
        requested_by="tester",
        params={"ports": "not-a-port"},
    )
    await session.commit()
    observed_statuses = []

    async def observe_committed_status(updated_job):
        async with AsyncSession(bind=session.bind) as observer:
            observed_statuses.append(await observer.scalar(
                select(ScanJob.status).where(ScanJob.id == updated_job.id)
            ))

    runner = ScanRunner(session, status_callback=observe_committed_status)
    with pytest.raises(ValueError):
        await runner.run_job(job.id)

    await session.refresh(job)
    assert job.status == JobStatus.failed
    assert job.error
    assert job.finished_at is not None
    assert observed_statuses == [JobStatus.running, JobStatus.failed]


# --- search DSL on real data -----------------------------------------------

async def _seed(session, eid):
    """Insert synthetic hosts/services covering all DSL features."""
    h_pub = Host(engagement_id=eid, ip="203.0.113.10", country="UA",
                 as_org="Example UA Telecom", asn=64500, tags=["ipv4", "global"])
    h_int = Host(engagement_id=eid, ip="10.0.0.5", country=None,
                 tags=["ipv4", "rfc1918", "private"])
    session.add_all([h_pub, h_int])
    await session.flush()

    session.add_all([
        Service(host_id=h_pub.id, port=443, transport=Transport.tcp,
                product="nginx", version="1.24.0",
                cpe=["cpe:2.3:a:nginx:nginx:1.24.0:*:*:*:*:*:*:*"],
                banner=None, tls={"subject": {"CN": "example.ua"}},
                data={"fingerprint": {"service": "http"}}),
        Service(host_id=h_pub.id, port=22, transport=Transport.tcp,
                product="OpenSSH", version="9.6p1",
                cpe=["cpe:2.3:a:openbsd:openssh:9.6p1:*:*:*:*:*:*:*"],
                banner="SSH-2.0-OpenSSH_9.6p1 admin gateway",
                data={"fingerprint": {"service": "ssh"}}),
        Service(host_id=h_int.id, port=5432, transport=Transport.tcp,
                product=None, version=None, cpe=[], banner=None,
                data={"fingerprint": {"service": "postgresql"}}),
        Service(host_id=h_int.id, port=6379, transport=Transport.tcp,
                product="Redis", version="7.2.4",
                cpe=["cpe:2.3:a:redis:redis:7.2.4:*:*:*:*:*:*:*"],
                banner="redis_version:7.2.4 admin",
                data={"fingerprint": {"service": "redis"}}),
    ])
    await session.commit()


@pytest.mark.asyncio
async def test_search_dsl_features(session):
    eid = await _make_engagement(session)
    await _seed(session, eid)

    async def q(s):
        return await search(session, eid, s)

    # exact product
    r = await q("product:nginx")
    assert len(r) == 1 and r[0].port == 443 and r[0].host.country == "UA"

    # port comparison
    r = await q("port:>1000")
    assert {s.port for s in r} == {5432, 6379}

    # port range
    r = await q("port:1-1024")
    assert {s.port for s in r} == {443, 22}

    # country + has_tls
    r = await q("country:UA has_tls:true")
    assert {s.port for s in r} == {443}

    # CIDR containment (internal subnet)
    r = await q("net:10.0.0.0/8")
    assert {s.port for s in r} == {5432, 6379}

    # tag
    r = await q("tag:rfc1918")
    assert all("rfc1918" in s.host.tags for s in r)

    # service via JSONB
    r = await q("service:postgresql")
    assert {s.port for s in r} == {5432}

    # cpe substring
    r = await q("cpe:openssh")
    assert {s.port for s in r} == {22}

    # negation
    r = await q("port:>1 -product:nginx")
    assert 443 not in {s.port for s in r}

    # full-text (banner/product/version weighted vector)
    r = await q("admin")
    ports = {s.port for s in r}
    assert 22 in ports and 6379 in ports  # both mention "admin"

    # combined
    r = await q("country:UA port:1-1024 admin")
    assert {s.port for s in r} == {22}
