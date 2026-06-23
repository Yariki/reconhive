---
name: local-dev-docker
description: Use when creating or modifying Dockerfiles, docker-compose.yml, local service dependencies, containers, healthchecks, volumes, ports, or dev infrastructure.
---


# Docker / Docker Compose Best Practices

## Dockerfiles

- Use explicit base image versions.
- Keep images small and reproducible.
- Use multi-stage builds for compiled apps.
- Run as non-root where practical.
- Copy dependency manifests before source code to improve cache use.
- Do not bake secrets into images.
- Add healthchecks for long-running services when useful.

## Docker Compose

- Use named volumes for durable local data.
- Use healthchecks and dependency readiness where possible.
- Expose only needed ports.
- Keep local credentials in `.env` and commit `.env.example` only.
- Avoid relying only on `depends_on`; it controls start order, not readiness unless health conditions are configured.

## Database Containers

- Pin versions for PostgreSQL and SQL Server images.
- Persist database data in named volumes.
- Provide init scripts only for local/dev seed behavior.
- Do not mount production backups casually into dev without data-handling controls.

## Verification

```bash
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=200
```

## Anti-Patterns

- `latest` tags for important images.
- Secrets in Dockerfile or compose file.
- Containers that require manual shell steps after startup.
- Mapping broad host directories into containers without reason.
