# Code Review Checklist for Codex

## Correctness

- Does the change solve the stated problem?
- Are edge cases handled?
- Are errors propagated or translated correctly?
- Are null/None/undefined cases handled deliberately?

## Architecture

- Is the change in the right layer?
- Are abstractions necessary and simple?
- Does the change avoid circular dependencies?
- Is business logic testable without HTTP/UI/infrastructure?

## Security

- Are authorization checks enforced server-side?
- Are SQL queries parameterized?
- Are secrets excluded from logs and source control?
- Are uploaded or external inputs validated?

## Database

- Is the migration safe?
- Are indexes justified by query patterns?
- Are large data changes batched?
- Are tenant filters and soft-delete filters preserved?

## Performance

- Any N+1 queries?
- Any unbounded lists?
- Any sync-over-async blocking?
- Any large objects loaded unnecessarily?

## Tests

- Are tests added at the right level?
- Do tests cover success, failure, and authorization paths?
- Are tests deterministic?

## Maintainability

- Is naming precise?
- Is dead code removed?
- Are comments useful?
- Is the diff smaller than necessary?
