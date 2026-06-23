# Verification Commands

Use the commands that match the project. Prefer repository scripts over generic commands.

## .NET

```bash
dotnet restore
dotnet format --verify-no-changes
dotnet build --no-restore
dotnet test --no-build
```

## Python with uv

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

## Alembic

```bash
uv run alembic current
uv run alembic heads
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

## TypeScript / React / Vue / Vite

```bash
npm ci
npm run typecheck
npm run lint
npm run test
npm run build
```

## Docker Compose

```bash
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=200
```
