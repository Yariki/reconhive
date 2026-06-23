---
name: software-architecture
description: Use when designing or refactoring system architecture, service boundaries, modules, repositories, queues, eventing, caching, search, or data pipelines.
---


# Software Architecture Best Practices

## Design Principles

- Start from use cases, data ownership, scale, failure modes, and security boundaries.
- Prefer simple modular monoliths until independent deployment/scaling is clearly needed.
- Make service boundaries align with domain ownership and data ownership.
- Avoid distributed transactions where possible.
- Use explicit contracts between modules/services.
- Keep synchronous request chains short.

## Layering

Typical backend layering:

1. API/transport layer
2. Application/use-case layer
3. Domain/business rules
4. Persistence/infrastructure adapters
5. External systems

Dependencies should point inward or through interfaces/protocols, not from domain to infrastructure.

## Data and Consistency

- Define source of truth for each entity.
- Define consistency requirements per workflow.
- Use transactions inside one database boundary.
- Use outbox/inbox patterns for reliable event publishing where needed.
- Design idempotent consumers.

## Queues and Background Work

- Use queues for durable, retryable, slow, or external-side-effect work.
- Define retry policy, dead-letter handling, idempotency, and observability.
- Do not hide critical user-facing failures in fire-and-forget jobs.

## Caching

- Cache only after identifying read pressure or latency need.
- Define invalidation and TTL before implementing.
- Do not cache unauthorized data without including auth/tenant context in the cache key.

## Search

- Keep security filters in the search path.
- Use database search for simple/moderate needs.
- Use Elasticsearch/OpenSearch for advanced full-text/search workloads.
- Use vector search for semantic retrieval only with clear evaluation criteria.

## Architecture Deliverables

For architecture tasks, produce:

- Context and assumptions.
- Component diagram or textual equivalent.
- Data flow.
- Security/RBAC model.
- Failure modes.
- Operational concerns.
- Implementation phases.
- Open questions and trade-offs.
