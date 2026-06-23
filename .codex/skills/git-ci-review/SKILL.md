---
name: git-ci-review
description: Use when preparing commits, pull requests, CI configuration, GitHub Actions/Azure DevOps pipelines, code review, branch safety, or release readiness.
---


# Git, CI, and Review Best Practices

## Commits

- Keep commits logically focused.
- Do not mix formatting-only changes with behavior changes unless unavoidable.
- Do not commit secrets, local configs, build outputs, or dependency caches.
- Include migration files with the model/schema changes that require them.

## Pull Requests

PR summary should include:

- What changed.
- Why it changed.
- How it was verified.
- Risk/rollback notes.
- Screenshots for UI changes where useful.

## CI

- Use deterministic install commands: `npm ci`, `uv sync --locked`, `dotnet restore`.
- Run format/lint/typecheck/test/build.
- Separate fast checks from slow integration/e2e checks if needed.
- Cache dependencies safely, keyed by lockfiles.
- Never print secrets in logs.

## Review Focus

- Correctness and edge cases.
- Security and authorization.
- Migration safety.
- API compatibility.
- Performance regressions.
- Test quality.
- Unnecessary dependencies or large diffs.

## Release Readiness

- Database migrations tested.
- Backward compatibility considered for rolling deployments.
- Feature flags used for risky changes when appropriate.
- Observability added for new critical flows.
- Rollback path known.
