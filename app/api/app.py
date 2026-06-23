"""FastAPI application factory."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import audit, engagements, hosts, jobs, search

_ALEMBIC_INI = Path(__file__).parent.parent.parent / "alembic.ini"


def _run_migrations() -> None:
    command.upgrade(Config(str(_ALEMBIC_INI)), "head")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    await asyncio.to_thread(_run_migrations)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="ReconHive API",
        version="0.1.0",
        description="Authorized reconnaissance & search. Every scan is scope-gated.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(engagements.router)
    app.include_router(jobs.router)
    app.include_router(hosts.router)
    app.include_router(search.router)
    app.include_router(audit.router)
    return app


app = create_app()
