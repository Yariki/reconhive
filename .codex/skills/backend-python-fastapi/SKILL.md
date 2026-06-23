---
name: backend-python-fastapi
description: Use when modifying Python FastAPI services, Pydantic schemas, API routes, dependency injection, lifespan, middleware, or async endpoints.
---


# Python / FastAPI Best Practices

## Project Structure

Prefer a feature or layer structure that separates:

- `api/` routes and dependency wiring
- `schemas/` Pydantic request/response contracts
- `services/` business use cases
- `repositories/` or `db/queries/` persistence logic
- `models/` SQLAlchemy ORM models
- `core/` settings, logging, security, errors
- `tests/` unit and integration tests

## Endpoint Rules

- Keep route handlers thin.
- Use Pydantic models for request and response boundaries.
- Use `response_model` for public endpoints when appropriate.
- Do not return ORM entities directly from public APIs.
- Inject dependencies with `Depends` or `Annotated[..., Depends(...)]` consistently.
- Use lifespan events for startup/shutdown, not ad hoc global initialization.
- Use `BackgroundTasks` only for short non-critical tasks; use a real queue for durable work.

## Async Rules

- Use `async def` only when the path performs async I/O.
- Do not call blocking libraries inside async endpoints.
- For CPU-bound work, move to worker process/thread pool or background worker.
- Propagate cancellation/timeouts where the stack supports it.

## Validation and Serialization

- Use separate schemas for create, update, read, and internal models.
- Use constrained types for bounded values.
- Treat Pydantic validation as boundary validation, not as a replacement for domain rules.
- Avoid leaking internal fields like password hashes, soft-delete flags, tenant internals.

## Error Handling

- Centralize exception-to-response mapping.
- Return consistent error envelopes or `HTTPException` patterns already used by the repo.
- Do not expose raw tracebacks to clients.
- Log exceptions with request correlation IDs when available.

## Security

- Enforce tenant/user authorization in services or query layer.
- Never trust user-supplied tenant/user IDs without verifying access.
- Use secure password hashing when handling credentials.
- Use explicit CORS origins.
- Do not load secrets from committed config.

## Verification

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

## Anti-Patterns

- Business logic in route functions.
- Global database sessions.
- Blocking `requests`, file I/O, or heavy CPU work in async routes.
- Returning SQLAlchemy models directly.
- Catch-all exception handlers that hide failures.
