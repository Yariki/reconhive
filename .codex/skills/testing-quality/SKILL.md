---
name: testing-quality
description: Use when adding tests, fixing flaky tests, improving coverage, designing unit/integration/e2e test strategy, or configuring lint/type/build gates.
---


# Testing and Quality Best Practices

## Test Pyramid

- Many fast unit tests for pure logic.
- Focused integration tests for database, API, and infrastructure boundaries.
- A smaller number of end-to-end tests for critical user journeys.

## Unit Tests

- Test behavior, not private implementation details.
- Keep tests deterministic.
- Avoid sleeps; use fake clocks or explicit synchronization.
- Avoid shared mutable fixtures.

## Integration Tests

- Use the real database engine for database behavior when possible.
- Run migrations before integration tests.
- Use isolated schemas/databases/transactions per test suite.
- Verify authorization and multi-tenant filtering.

## Frontend Tests

- Prefer user-facing queries and interactions.
- Test forms, validation, loading, error, and empty states.
- Mock network at the boundary.
- Avoid snapshot-only tests for complex behavior.

## Quality Gates

Use all that apply:

```bash
# Python
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest

# .NET
dotnet format --verify-no-changes
dotnet build
dotnet test

# TypeScript
npm run typecheck
npm run lint
npm run test
npm run build
```

## Flakiness Rules

- Reproduce before changing broad code.
- Identify timing, isolation, random data, timezone, network, or dependency causes.
- Fix root cause; do not simply increase timeouts unless justified.
