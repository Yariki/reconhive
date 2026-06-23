"""Unit tests for the in-process job WebSocket fan-out."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.api import job_events


class FakeWebSocket:
    def __init__(self, *, fail: bool = False) -> None:
        self.accepted = False
        self.fail = fail
        self.send_count = 0
        self.messages: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        self.send_count += 1
        if self.fail:
            raise RuntimeError("socket closed")
        self.messages.append(message)


@pytest.mark.asyncio
async def test_hub_fans_out_by_engagement_and_prunes_closed_sockets(monkeypatch):
    first_engagement = uuid.uuid4()
    second_engagement = uuid.uuid4()
    healthy = FakeWebSocket()
    closed = FakeWebSocket(fail=True)
    unrelated = FakeWebSocket()
    hub = job_events.JobEventHub()

    monkeypatch.setattr(job_events, "job_payload", lambda job: {"id": job.id})
    await hub.connect(first_engagement, healthy)  # type: ignore[arg-type]
    await hub.connect(first_engagement, closed)  # type: ignore[arg-type]
    await hub.connect(second_engagement, unrelated)  # type: ignore[arg-type]

    job = SimpleNamespace(id="job-1", engagement_id=first_engagement)
    await hub.publish_job(job)  # type: ignore[arg-type]

    assert healthy.accepted and healthy.messages == [
        {"type": "job.updated", "job": {"id": "job-1"}}
    ]
    assert closed.send_count == 1
    assert unrelated.messages == []

    await hub.publish_job(job)  # type: ignore[arg-type]
    assert closed.send_count == 1  # removed after the failed write
    assert len(healthy.messages) == 2
