"""API integration tests (httpx ASGITransport) against a real PostgreSQL.

Skipped if no PostgreSQL is reachable.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api import create_app
from app.db.session import SessionFactory, engine

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
async def client() -> AsyncClient:
    async with SessionFactory() as s:
        await s.execute(text(
            "TRUNCATE audit_log, services, hosts, scan_jobs, scope_entries, "
            "engagements RESTART IDENTITY CASCADE"
        ))
        await s.commit()
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    # The engine pool is bound to this test's event loop; drop it so the next
    # test (new loop) gets fresh connections.
    await engine.dispose()


def _engagement_body():
    now = datetime.now(UTC)
    return {
        "client_name": "Acme Corp",
        "authorization_ref": "SOW-2026-API",
        "starts_at": (now - timedelta(days=1)).isoformat(),
        "ends_at": (now + timedelta(days=30)).isoformat(),
    }


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_full_flow(client):
    # 1. create engagement
    r = await client.post("/engagements", json=_engagement_body())
    assert r.status_code == 201
    eid = r.json()["id"]

    # 2. add scope
    r = await client.post(f"/engagements/{eid}/scope",
                          json={"cidr": "127.0.0.0/8", "kind": "allow"})
    assert r.status_code == 201

    # 3. localhost SSH listener
    async def ssh(reader, writer):
        writer.write(b"SSH-2.0-OpenSSH_9.6p1 Ubuntu\r\n")
        await writer.drain()
        await asyncio.sleep(0.05)
        writer.close()

    server = await asyncio.start_server(ssh, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        # 4. plan job
        r = await client.post(f"/engagements/{eid}/jobs", json={
            "job_type": "banner_grab", "targets": ["127.0.0.1/32"], "ports": [port],
        })
        assert r.status_code == 201, r.text
        job = r.json()
        assert job["authorized_targets"] == ["127.0.0.1/32"]
        assert job["status"] == "pending"
        job_id = job["id"]

        # 5. run inline
        r = await client.post(f"/jobs/{job_id}/run", params={"wait": "true"})
        assert r.status_code == 200, r.text
        done = r.json()
        assert done["status"] == "completed"
        assert done["stats"]["hosts_up"] == 1

        # A completed job cannot be claimed a second time.
        r = await client.post(f"/jobs/{job_id}/run")
        assert r.status_code == 409
    finally:
        server.close()
        await server.wait_closed()

    # 6. search via DSL
    r = await client.get(f"/engagements/{eid}/search", params={"q": "product:OpenSSH"})
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["service"]["product"] == "OpenSSH"
    assert results[0]["service"]["version"] == "9.6p1"
    assert results[0]["host"]["ip"].startswith("127.0.0.1")

    # 7. hosts list + detail
    r = await client.get(f"/engagements/{eid}/hosts")
    assert r.status_code == 200 and len(r.json()) == 1
    host_id = r.json()[0]["id"]
    r = await client.get(f"/hosts/{host_id}")
    assert r.status_code == 200 and len(r.json()["services"]) == 1

    # 8. audit trail
    r = await client.get(f"/engagements/{eid}/audit")
    actions = {row["action"] for row in r.json()}
    assert {"job_submitted", "job_started", "job_finished"} <= actions


@pytest.mark.asyncio
async def test_out_of_scope_job_rejected(client):
    r = await client.post("/engagements", json=_engagement_body())
    eid = r.json()["id"]
    await client.post(f"/engagements/{eid}/scope",
                      json={"cidr": "127.0.0.0/8", "kind": "allow"})
    r = await client.post(f"/engagements/{eid}/jobs",
                          json={"targets": ["10.0.0.0/24"]})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_bad_search_query_400(client):
    r = await client.post("/engagements", json=_engagement_body())
    eid = r.json()["id"]
    r = await client.get(f"/engagements/{eid}/search", params={"q": "bogus:value"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_unknown_engagement_404(client):
    r = await client.get("/engagements/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
