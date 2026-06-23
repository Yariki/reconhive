---
name: security-rbac-multitenancy
description: Use when implementing authentication, authorization, RBAC, ABAC, tenant isolation, row-level access, secrets handling, or secure API behavior.
---


# Security, RBAC, and Multi-Tenancy Best Practices

## Authorization Model

- Authenticate identity first.
- Authorize every resource action server-side.
- Use deny-by-default.
- Model permissions explicitly: subject, action, resource, scope, tenant.
- Keep admin bypasses explicit and auditable.
- Check ownership and group membership at query time for restricted data.

## Multi-Tenancy

- Every tenant-owned table should have tenant identity or a clear tenant path.
- Apply tenant filters in repositories/query builders/services.
- Add tests proving cross-tenant access is denied.
- Do not trust tenant IDs supplied by the client without checking membership.

## Secrets

- Store secrets in environment, secret manager, or local uncommitted `.env`.
- Commit `.env.example` with safe placeholders.
- Never log secrets or full authorization headers.
- Rotate credentials if exposed.

## Input Handling

- Validate body, query, path, headers, and uploaded files.
- Use allow-lists for sorting/filtering fields.
- Limit request size and upload size.
- Sanitize or encode output in UI contexts.

## Database Security

- Use parameterized SQL.
- Avoid dynamic SQL from user input.
- Use least-privilege database users.
- Preserve authorization predicates in search queries.

## Review Checklist

- Can a user access another tenant’s data?
- Can a user change owner/admin fields?
- Can a deleted/disabled user still access data?
- Are sensitive fields returned in API responses?
- Are audit logs sufficient for privileged actions?
