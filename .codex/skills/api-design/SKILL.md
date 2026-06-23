---
name: api-design
description: Use when designing REST APIs, OpenAPI contracts, pagination, filtering, error models, versioning, idempotency, or client-server contracts.
---


# API Design Best Practices

## Resource Design

- Use nouns for resources and stable URL patterns.
- Keep actions rare; model state transitions deliberately.
- Version public APIs explicitly when compatibility matters.
- Keep request and response DTOs separate.

## HTTP Semantics

- Use methods consistently: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`.
- Use correct status codes.
- Use `201 Created` with location/body for created resources when practical.
- Use `409 Conflict` for business conflicts.
- Use `404` carefully to avoid leaking unauthorized resource existence when needed.

## Pagination and Filtering

- Every collection endpoint must be paginated.
- Use deterministic ordering.
- Prefer cursor/keyset pagination for large/deep collections.
- Validate filters and sorting fields against allow-lists.

## Errors

- Return consistent error envelopes.
- Include machine-readable error codes.
- Include field-level validation errors.
- Do not expose stack traces or raw SQL/provider errors.

## Idempotency

- Use idempotency keys for retryable operations that create external side effects.
- Make delete operations safe to retry when possible.
- Avoid duplicate side effects on client retry or network timeout.

## OpenAPI

- Keep schemas accurate.
- Include auth requirements.
- Include examples for non-trivial payloads.
- Generate clients from OpenAPI when the workflow supports it.

## Security

- Authenticate first, authorize per resource/action.
- Apply tenant filters server-side.
- Rate-limit public or expensive endpoints.
- Validate content-type and payload size.
