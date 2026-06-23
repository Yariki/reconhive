---
name: database-sqlserver
description: Use when designing SQL Server schema, indexes, stored procedures, T-SQL queries, migrations, execution plans, locking, or performance tuning.
---


# SQL Server Best Practices

## Schema Design

- Enforce invariants with constraints.
- Use appropriate data types; avoid oversized `nvarchar(max)`/`varbinary(max)` unless needed.
- Choose clustered keys deliberately; avoid random wide clustered keys for heavy insert tables unless justified.
- Use schemas to separate domains when helpful.
- Store UTC or clearly documented timezone-aware timestamps.

## Indexing

- Design indexes from workload: predicates, joins, sorting, grouping, and uniqueness.
- Avoid both missing indexes and over-indexing.
- Consider included columns for covering important read queries.
- Watch write amplification from too many nonclustered indexes.
- Review actual execution plans, not only estimated plans, for performance issues.

## Querying

- Use parameterized queries.
- Keep predicates sargable.
- Avoid wrapping indexed columns in functions in `WHERE` when it prevents seeks.
- Avoid `SELECT *` in production hot paths.
- Use pagination with deterministic ordering.
- Avoid `NOLOCK` as a default. It can return dirty, duplicated, or missing rows.

## Transactions and Locking

- Keep transactions short.
- Use appropriate isolation level for the business requirement.
- Handle deadlocks with retry where safe.
- Avoid long-running migrations in business hours for large tables.

## Migrations

- Review generated SQL.
- For large table changes, use phased deployment and backfills.
- Add indexes online where edition/version supports it and the project policy allows it.
- Include rollback strategy for risky schema changes.

## Verification

- Inspect actual execution plans.
- Compare logical reads and duration before/after.
- Run integration tests against SQL Server, not only in-memory substitutes.

## Anti-Patterns

- `NOLOCK` everywhere.
- Non-sargable filters.
- Scalar UDFs in hot row-by-row paths.
- Excessive triggers for business logic.
- Missing unique constraints for business keys.
