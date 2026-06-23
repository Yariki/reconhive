---
name: backend-dotnet-aspnetcore
description: Use when modifying .NET, ASP.NET Core, C#, Web API, Minimal API, controllers, middleware, options, DI, hosted services, or authentication.
---


# .NET / ASP.NET Core Best Practices

## Architecture

- Keep endpoints/controllers thin: validate, authorize, call application service, map response.
- Put business logic in application/domain services, not controllers.
- Use dependency injection for services, repositories, clients, and options.
- Use `IOptions<T>`, `IOptionsSnapshot<T>`, or `IOptionsMonitor<T>` for configuration.
- Use typed `HttpClient` via `IHttpClientFactory` for outbound HTTP.
- Use middleware for cross-cutting request behavior.
- Use filters only for scoped MVC/API concerns.

## Async and Performance

- Use async I/O end-to-end for database, file, HTTP, and network calls.
- Never block async code with `.Result`, `.Wait()`, or `Task.Run` around I/O.
- Pass `CancellationToken` from endpoint to service to database/client calls.
- Use pagination for all collection endpoints.
- Stream large responses where appropriate.
- Avoid returning large object graphs.

## Error Handling

- Use centralized exception handling middleware.
- Return RFC 7807 `ProblemDetails`-style errors where possible.
- Do not expose stack traces or internal exception messages to clients.
- Log with structured properties, not interpolated strings for critical metadata.

## Security

- Enforce authorization server-side in policies/services.
- Use `[Authorize]` or endpoint authorization conventions by default.
- Use antiforgery protection for cookie-authenticated browser form workflows.
- Validate JWT issuer, audience, lifetime, and signing keys.
- Do not log tokens, claims dumps, passwords, connection strings, or PII.

## Data Contracts

- Separate request/response DTOs from EF entities.
- Validate DTOs using DataAnnotations, FluentValidation, or endpoint filters as used by the repo.
- Keep DTO versioning explicit for public APIs.

## Testing

- Unit-test services and pure domain logic.
- Integration-test API behavior with `WebApplicationFactory` when available.
- Test authorization paths: anonymous, wrong role, wrong tenant, owner, admin.

## Verification

```bash
dotnet restore
dotnet format --verify-no-changes
dotnet build --no-restore
dotnet test --no-build
```

## Anti-Patterns

- Fat controllers.
- Static service access.
- Hidden dependencies through `IServiceProvider` in business code.
- Sync-over-async.
- Returning EF entities directly from public APIs.
- Catching `Exception` and returning success.
