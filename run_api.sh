#!/usr/bin/env bash
# Start the ReconHive API. Requires a running PostgreSQL (see docker-compose.yml)
# and the schema loaded (db/schema.sql or `alembic upgrade head`).
export RECONHIVE_DATABASE_URL="${RECONHIVE_DATABASE_URL:-postgresql+asyncpg://reconhive:reconhive@localhost:5432/reconhive}"
exec uvicorn app.api.app:app --reload --port 8000
