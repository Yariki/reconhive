---
name: database-postgresql
description: Use when designing PostgreSQL schema, indexes, SQL queries, migrations, JSONB, full-text search, pgvector, partitions, locking, or query performance.
---


# PostgreSQL Best Practices

## Schema Design

- Model core invariants with constraints: `NOT NULL`, `UNIQUE`, `CHECK`, `FOREIGN KEY`.
- Use normalized relational tables for structured data with stable schema.
- Use `jsonb` for flexible attributes only when query/update patterns justify it.
- Use `uuid` or identity keys according to project convention.
- Store timestamps with timezone semantics; prefer `timestamptz` for event times.
- Include tenant identifiers in multi-tenant tables and indexes where required.

## Indexing

- Add indexes for actual query predicates, joins, sorting, and uniqueness.
- Avoid over-indexing; every index adds write and maintenance cost.
- Use composite indexes with column order based on query patterns.
- Use partial indexes for filtered common cases.
- Use GIN indexes for suitable `jsonb`, array, full-text, or trigram use cases.
- Use `EXPLAIN` / `EXPLAIN ANALYZE` before and after optimizing hot queries.

## Querying

- Avoid unbounded result sets.
- Avoid `SELECT *` in hot paths.
- Use keyset pagination for deep pagination.
- Keep filters sargable.
- Use transactions deliberately; keep them short.
- Use row-level locking only when necessary and understand contention.

## Migrations

- For large tables, avoid table rewrites and long exclusive locks.
- Add nullable columns first; backfill; validate; then add `NOT NULL`.
- Consider concurrent index creation where supported and compatible with the migration tool.
- Split risky migrations into deployable phases.

## Full-Text and Semantic Search

- Use PostgreSQL full-text search for moderate built-in lexical search.
- Use trigram indexes for fuzzy matching.
- Use pgvector only when vector search requirements justify operational complexity.
- Keep ACL/tenant filters in the query path before returning results.

## Verification

```sql
EXPLAIN (ANALYZE, BUFFERS) <query>;
```

Also verify migrations against a database with realistic data volume when possible.

## Anti-Patterns

- Indexing every foreign key and every text column blindly.
- Relying on application checks instead of database constraints.
- Long transactions during batch jobs.
- Multi-tenant queries without tenant filters.
