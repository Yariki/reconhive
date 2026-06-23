---
name: frontend-typescript
description: Use when modifying TypeScript code, tsconfig, typed API clients, domain models, type guards, unions, or frontend build typing.
---


# TypeScript Best Practices

## Compiler Settings

- Use `strict: true` unless the repository is in a staged migration.
- Keep `noImplicitAny`, `strictNullChecks`, and `noUncheckedIndexedAccess` enabled for new serious applications when practical.
- Use project references for large monorepos when needed.
- Run type checking separately from Vite build.

## Type Modeling

- Prefer domain-specific types over primitive obsession.
- Use discriminated unions for variants and state machines.
- Use `unknown` for untrusted external data, then narrow or validate.
- Use type guards for runtime checks.
- Prefer `interface` for object contracts and `type` for unions/intersections when consistent with repo style.
- Use `readonly` for immutable data structures where useful.

## API Boundaries

- Treat JSON responses as untrusted.
- Generate clients from OpenAPI when the project supports it.
- Keep request/response DTOs separate from UI state types.
- Normalize date/time handling; do not rely on implicit local timezone conversions.

## Avoid

- `any` except at deliberate escape hatches.
- Double casts like `value as unknown as T` without strong reason.
- Non-null assertions `!` where a proper guard is possible.
- Enum overuse when literal unions are enough.
- Mutating function arguments unexpectedly.

## Verification

```bash
npm run typecheck
npm run lint
npm run test
npm run build
```

If no script exists, inspect `package.json` and use the project equivalent, such as:

```bash
npx tsc --noEmit
```
