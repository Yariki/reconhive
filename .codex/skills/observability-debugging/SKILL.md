---
name: observability-debugging
description: Use when debugging failures, adding logs, metrics, tracing, health checks, or diagnosing performance/timeouts in backend, frontend, or infrastructure.
---


# Observability and Debugging Best Practices

## Debugging Flow

1. Reproduce the issue or identify why it cannot be reproduced.
2. Capture exact error message, stack trace, request, input, environment, and version.
3. Narrow scope with logs/tests/bisecting.
4. Fix the root cause, not only the symptom.
5. Add regression coverage.
6. Remove temporary debug output.

## Logging

- Use structured logs.
- Include correlation/request IDs.
- Log domain-relevant identifiers, not entire payloads.
- Do not log secrets or PII.
- Use levels consistently: debug, info, warning, error.

## Metrics

- Track latency, throughput, errors, queue depth, retries, and saturation.
- Use histograms for latency.
- Add domain metrics for critical workflows.
- Avoid high-cardinality labels such as raw user IDs, emails, or URLs unless explicitly approved.

## Tracing

- Trace external calls, database queries, queues, and important internal operations.
- Propagate context across services.
- Add spans around expensive or failure-prone work.

## Health Checks

- Liveness: process is alive.
- Readiness: dependencies required to serve traffic are available.
- Startup: slow initialization finished.

## Performance Triage

- Measure before optimizing.
- Separate CPU, I/O, database, network, lock contention, and client rendering causes.
- For database issues, inspect execution plans.
- For frontend issues, profile rendering and bundle size.
