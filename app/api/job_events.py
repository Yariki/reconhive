"""In-process WebSocket fan-out for scan job updates.

The API currently runs as a single uvicorn worker, so an in-memory hub keeps
the implementation small.  The public interface is deliberately tiny so it
can later be backed by Redis pub/sub without changing the routers or runner.
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi import WebSocket

from ..db.models import ScanJob
from .schemas import ScanJobOut


def job_payload(job: ScanJob) -> dict:
    """Return the JSON-safe representation shared by HTTP and WebSockets."""
    return ScanJobOut.model_validate(job).model_dump(mode="json")


class JobEventHub:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = {}

    async def connect(self, engagement_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(engagement_id, set()).add(websocket)

    def disconnect(self, engagement_id: uuid.UUID, websocket: WebSocket) -> None:
        sockets = self._connections.get(engagement_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            self._connections.pop(engagement_id, None)

    async def publish_job(self, job: ScanJob) -> None:
        sockets = list(self._connections.get(job.engagement_id, ()))
        if not sockets:
            return

        event = {"type": "job.updated", "job": job_payload(job)}

        async def send(websocket: WebSocket) -> None:
            try:
                await websocket.send_json(event)
            except Exception:  # disconnected clients are pruned on write
                self.disconnect(job.engagement_id, websocket)

        await asyncio.gather(*(send(websocket) for websocket in sockets))


job_event_hub = JobEventHub()
