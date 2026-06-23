# CLAUDE.md — User-Level Instructions

> Global preferences applied across all projects. Project-specific `CLAUDE.md`
> files override or extend anything here.

## About Me

I'm a senior software developer and architect. Treat me as a peer: be direct,
skip basic explanations unless I ask, and don't pad responses with caveats or
encouragement. If something I propose is wrong or risky, say so plainly and
explain why. I prefer being corrected over being agreed with.

When I ask "how" or "why," give the reasoning and the trade-offs, not just the
answer. When I ask for code, give me production-quality code, not a toy example.

## Languages & Stacks

**Primary:**
- **Python** — FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, asyncio
- **C# / .NET** — modern .NET (current LTS), async/await throughout
- **TypeScript** — Vue 3 (Composition API, `<script setup>`), Vuetify 3

**Embedded / IoT:**
- ESP32, Arduino, Raspberry Pi — C/C++ (Arduino/ESP-IDF) and Python where it fits

**Data & messaging:**
- **PostgreSQL** (preferred) and **SQL Server**
- **RabbitMQ** with `aio-pika` as the async client

Default to these unless a project says otherwise. Don't introduce a new language,
framework, or heavy dependency without flagging it and giving a reason.

## Code Standards

- Write code as if it's going to production: handle errors, edge cases, and
  resource cleanup. No `# TODO: handle this later` in the happy path.
- Prefer explicit over clever. Readability and maintainability win over brevity.
- Type everything: Python type hints (and `mypy`-clean where practical),
  TypeScript strict mode, C# nullable reference types enabled.
- Keep functions small and single-purpose; push side effects to the edges.
- Don't add comments that restate the code. Comment the *why*, not the *what*.
- Follow the conventions already present in a file or project over my generic
  preferences here. Match existing style before imposing a new one.

## Best Practices by Technology

Apply these by default. They're the conventions I want followed unless a project
explicitly diverges.

### Python / FastAPI / SQLAlchemy
- `async`/`await` end-to-end; never block the event loop. Wrap unavoidable
  blocking calls in `asyncio.to_thread`.
- **SQLAlchemy 2.0 style only**: `select()`, `Mapped[...]` / `mapped_column`,
  `AsyncSession`. No legacy `Query` API.
- One session per request scoped via FastAPI dependency injection; never share a
  session across tasks. Commit at the edge of the unit of work, not deep inside.
- Avoid lazy loading in async contexts — use `selectinload` / `joinedload`
  explicitly to prevent implicit IO and N+1 queries.
- **Pydantic v2** for request/response schemas and settings (`BaseSettings`).
  Keep ORM models and API schemas separate; map between them deliberately.
- FastAPI: typed dependencies, `response_model` on endpoints, routers per domain,
  `lifespan` for startup/shutdown (not deprecated event handlers).
- Pin dependencies; manage with `uv` or `poetry`. Format with `ruff format`,
  lint with `ruff`, type-check with `mypy`/`pyright`.
- Config from environment, never hard-coded; secrets never in source.
- Structured logging (JSON in prod); never log secrets or PII.

### C# / .NET
- Async all the way; never `.Result` / `.Wait()` / `.GetAwaiter().GetResult()`.
  Use `ConfigureAwait(false)` in libraries; pass `CancellationToken` through.
- Nullable reference types enabled; treat warnings as errors in CI.
- DI via the built-in container; depend on interfaces at boundaries. Register
  with correct lifetimes (singleton/scoped/transient) and avoid captive deps.
- Prefer `IOptions<T>` for config, `ILogger<T>` for logging, `HttpClientFactory`
  for HTTP (never `new HttpClient()` per call).
- Use records/`readonly`/immutability for DTOs; `Span<T>`/`Memory<T>` on hot paths.
- EF Core: `AsNoTracking()` for reads, explicit `Include`, compiled/parameterized
  queries, async methods. Watch for N+1 and client-side evaluation.
- `IAsyncEnumerable<T>` for streaming; `System.Text.Json` over Newtonsoft unless
  there's a reason.

### TypeScript / Vue 3 / Vuetify 3
- `strict` mode on; no implicit `any`. Type props, emits, and store state.
- Composition API with `<script setup lang="ts">`; extract reusable logic into
  composables (`useXxx`).
- Typed props/emits via `defineProps<T>()` / `defineEmits<T>()`.
- Pinia for state; keep stores focused. Avoid prop-drilling and giant components.
- Vuetify 3 components and theming over hand-rolled UI/CSS; respect the design
  system rather than fighting it.
- Keep side effects in `onMounted`/watchers, not in render; clean them up.
- ESLint + Prettier; `vue-tsc` in CI for type checking templates.

### PostgreSQL (preferred)
- Proper types: `timestamptz` (always store UTC), `numeric` for money, `uuid`,
  `jsonb` (not `json`), enums or lookup tables for fixed sets.
- Index intentionally: B-tree for equality/range, GIN for `jsonb`/full-text,
  partial and composite indexes to match real query predicates. Verify with
  `EXPLAIN (ANALYZE, BUFFERS)`.
- Concurrency: optimistic locking (version column), advisory locks for
  app-level coordination, `SELECT ... FOR UPDATE` where needed. For partial
  updates use JSONB `||` and `COALESCE` on nullable columns.
- Idempotent upserts via `INSERT ... ON CONFLICT DO UPDATE`.
- Constraints in the database (FKs, `CHECK`, `UNIQUE`, `NOT NULL`) — don't rely
  on app code alone. Migrations are versioned (Alembic / EF migrations) and
  reversible.
- Partition large tables; use connection pooling (PgBouncer / async pool).

### SQL Server
- Parameterized queries / stored procs only — never string-concatenated SQL.
- Mind clustered vs. nonclustered indexes; include columns to make covering
  indexes; check actual execution plans.
- Explicit transactions with appropriate isolation; consider
  `READ COMMITTED SNAPSHOT` to reduce blocking. Keep transactions short.
- `MERGE` with care (known edge cases); prefer explicit upsert patterns when in
  doubt. Use `OUTPUT` for capturing affected rows.
- `datetime2`/`datetimeoffset` over `datetime`; `decimal` for money.

### RabbitMQ (aio-pika)
- **At-least-once delivery** + **idempotent consumers** (dedup keys / idempotent
  upserts) so redelivery is safe.
- Publisher confirms on; manual consumer acks — ack only after successful
  processing, `nack`/reject to DLX on failure.
- Dead-letter exchanges for poison messages; bounded retries with backoff, not
  infinite requeue loops.
- Set `prefetch` (QoS) to control concurrency and avoid overwhelming consumers.
- `declare_infrastructure()` is idempotent and safe to run on every startup.
- Durable exchanges/queues + persistent messages for anything that matters.
- Treat broker connectivity as unreliable: reconnect with backoff, handle
  channel recovery.

### ESP32 / Arduino / Raspberry Pi
- Non-blocking loops: avoid `delay()`; use `millis()` timers or an RTOS task
  (FreeRTOS on ESP32). Keep ISRs tiny — set flags, defer work.
- Watch memory: prefer stack/static allocation, avoid heap fragmentation
  (`String` churn), check free heap. Use `PROGMEM`/flash for constants on AVR.
- Debounce inputs; use hardware timers/interrupts for precise timing.
- Wi-Fi/MQTT: reconnect logic with backoff, watchdog timer, brown-out awareness.
- Never hard-code Wi-Fi/API secrets in sketches committed to source.
- Pi: pin OS/package versions, run services under systemd, log to journald,
  and treat GPIO access with proper cleanup.

## Architecture Preferences

These reflect patterns I use repeatedly — apply them by default in distributed
and data-heavy systems:

- **At-least-once delivery** for messaging, paired with **idempotent consumers**
  (idempotent upserts, dedup keys) so reprocessing is safe.
- **Idempotent infrastructure setup** — declaring exchanges/queues/tables should
  be safe to run repeatedly.
- RabbitMQ: dead-letter exchanges, publisher confirms, sensible prefetch.
- **Audit logging** for security- and compliance-relevant actions.
- **Fail-closed** on authorization and access control — deny by default, and
  enforce scope/authorization *before* taking any external action.
- Separate services communicate via events/queues, not by reaching into each
  other's data.
- For Postgres concurrency: optimistic locking, advisory locks, JSONB `||` and
  `COALESCE` for partial updates where appropriate.

Before generating a non-trivial design, state the key assumptions and the main
trade-off you're optimizing for (e.g., consistency vs. availability, latency vs.
throughput). If there's a meaningful alternative, mention it in a sentence.

## Cross-Cutting Practices

Apply these across every stack, regardless of language.

### Security
- Secrets from environment / a secrets manager — never in source, logs, or
  committed config. Validate this hasn't slipped into a diff.
- Validate and sanitize all external input at the boundary; trust nothing from
  clients. Parameterized queries only (no string-built SQL).
- Authenticate then authorize on every protected path; **fail closed** (deny by
  default). Check authorization *before* performing the action.
- Hash passwords with a slow algorithm (argon2/bcrypt); never roll your own
  crypto. Short-lived tokens, least-privilege credentials.
- Encrypt in transit (TLS) and at rest where the data warrants it. Never log
  secrets or PII; redact at the logging boundary.
- Keep dependencies patched; scan for known CVEs in CI.

### Git / Version Control
- Small, focused commits with imperative, meaningful messages (Conventional
  Commits is fine). One logical change per commit.
- Short-lived feature branches; rebase/squash to keep history readable. Don't
  commit generated artifacts, secrets, or large binaries — maintain `.gitignore`.
- PRs are reviewable in size; describe the *why*. Don't force-push shared branches.

### CI / CD
- CI runs lint, type-check, tests, and security scan on every PR; main stays
  green and releasable.
- Build once, promote the same artifact across environments. No manual
  hand-editing in prod.
- Automated, reversible database migrations gated in the pipeline. Use the
  deploy checklist (migrations, flags, rollback plan) before shipping.
- Feature flags for risky changes; prefer progressive rollout over big-bang.

### Containers & Config
- Small, pinned base images; multi-stage builds; run as non-root; `.dockerignore`
  to keep contexts lean.
- One concern per container; configuration via environment, not baked-in.
- Health/readiness checks; explicit resource limits.
- Twelve-factor config: strict separation of config from code across all envs.

### API Design
- Consistent, versioned contracts. Correct HTTP semantics (status codes, verbs,
  idempotency for `PUT`/`DELETE`).
- Validate inputs, return structured, typed errors (a consistent error shape).
  Never leak stack traces or internals to clients.
- Pagination, filtering, and sane defaults on collection endpoints; rate limiting
  on public surfaces.
- Document with OpenAPI; keep request/response schemas explicit.

### Observability & Error Handling
- Structured logging (JSON in prod) with correlation/trace IDs across services.
- Metrics on the things that matter (latency, error rate, throughput, queue
  depth); alert on symptoms, not noise.
- Fail loud internally, degrade gracefully externally. Catch narrowly; never
  swallow exceptions silently. Use retries with backoff + circuit breakers for
  downstream calls, and make retried operations idempotent.

## Testing

- **Real integration tests over mocks.** I trust tests that run against live
  PostgreSQL / RabbitMQ (e.g., via `testcontainers`) far more than mocked units.
- Use `pytest-asyncio`; isolate tests with transaction rollback per test.
- Assume bugs are found by *running* code, not by static analysis alone — so make
  things runnable and testable.
- When you write a feature, write or update the tests for it in the same pass.

## Skills

Prefer these skills when a task matches their purpose — invoke them rather than
improvising from scratch. They encode workflows I want applied consistently.

**Engineering**
- `engineering:architecture` — ADRs and design decisions; documenting trade-offs
  and consequences (e.g., Kafka vs. SQS, sync vs. event-driven).
- `engineering:system-design` — designing services, APIs, data models, and
  service boundaries from requirements.
- `engineering:code-review` — reviewing a diff/PR for security, performance, and
  correctness; catching N+1 queries, injection, missing edge cases.
- `engineering:testing-strategy` — test plans, coverage, and test architecture;
  what to test and at which layer.
- `engineering:debug` — structured debugging: reproduce, isolate, diagnose, fix.
  Use for stack traces and "works in staging, not prod" cases.
- `engineering:tech-debt` — identifying, categorizing, and prioritizing refactors
  and code-health work.
- `engineering:deploy-checklist` — pre-deploy verification: migrations, feature
  flags, CI status, rollback triggers.
- `engineering:incident-response` — triage, comms, and blameless postmortems for
  production incidents.
- `engineering:documentation` — READMEs, runbooks, API and architecture docs
  (only when I ask for docs).
- `engineering:standup` — turning recent commits/PRs/tickets into a standup update.

**Data**
- `data:sql-queries` / `data:write-query` — correct, performant SQL across
  dialects (PostgreSQL, SQL Server, etc.); optimizing slow queries, CTEs,
  window functions.
- `data:explore-data` / `data:analyze` — profiling datasets, investigating
  trends, and answering data questions.
- `data:data-visualization` / `data:create-viz` — publication-quality charts
  with Python (matplotlib/seaborn/plotly).
- `data:statistical-analysis` — distributions, significance testing, outlier
  detection, correlations.
- `data:validate-data` — QA an analysis before sharing: methodology, accuracy,
  bias checks.
- `data:build-dashboard` — self-contained interactive HTML dashboards.

**Documents** (when a formatted file is the deliverable)
- `docx`, `pdf`, `pptx`, `xlsx` — generating or editing Word/PDF/PowerPoint/Excel
  files. Use only when a formatted file is explicitly the goal, not for inline
  answers.

If a relevant skill exists, use it; if none fits, proceed normally. Don't force a
skill onto a task it doesn't match.

## How to Work With Me

- **Phased, iterative delivery.** For large efforts, propose a roadmap of phases
  and deliver in increments rather than one giant dump.
- For multi-step or ambiguous tasks, briefly outline the plan before diving in,
  then proceed — don't wait for permission on obvious steps.
- Prefer editing existing files over creating new ones unless a new file is
  clearly warranted.
- Don't create documentation files (README, etc.) unless I ask.
- Show me the diff/changes concisely; don't re-print large unchanged blocks.
- If a request is underspecified in a way that materially affects the design,
  ask one focused question rather than guessing — but if a reasonable default
  exists, state it and move on.

## Formatting of Responses

- Lead with the answer or the code; keep prose tight.
- Use fenced code blocks with language tags.
- No filler ("Great question!", "I hope this helps!").
- Cite the trade-off or gotcha when one exists; I'd rather know the sharp edges.
