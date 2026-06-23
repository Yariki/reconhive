# ReconHive

ReconHive is an authorized network reconnaissance and search platform for
pentest engagements, internal asset discovery, and lab environments. It combines
engagement scope management, a hard pre-packet authorization gate, async TCP
connect scanning, service fingerprinting, enrichment, searchable PostgreSQL
storage, and a Vue 3 operator UI.

> ReconHive is for pentest engagements with written client authorization,
> internal asset discovery, and lab use. The Scope Guard is the central
> design element precisely because unauthorized internet-wide scanning is
> illegal in most jurisdictions. Every scan passes through it.

The main design goal is defense in depth: requested targets are filtered before
a job is queued, and each host is checked again immediately before the scanner
opens a socket. The audit log records scope decisions and job lifecycle events
so each engagement has a reviewable compliance trail.

## Architecture

ReconHive is a small modular application:

- **Frontend:** Vue 3 + Vite operator console for engagements, scope, jobs,
  live progress, hosts, search, and audit.
- **API:** FastAPI routers expose engagement/scope, scan jobs, search, hosts,
  audit, and WebSocket job updates.
- **Scope layer:** `ScopeService` loads persisted authorization rules and
  delegates CIDR math to the pure `ScopeGuard`.
- **Scan layer:** `ScanRunner` executes queued jobs through `TcpConnectScanner`,
  bounded concurrency, rate limiting, fingerprinting, enrichment, and upserts.
- **Persistence:** PostgreSQL stores engagement-scoped scope rules, jobs, hosts,
  services, search vectors, JSONB enrichment, and append-only audit records.

```mermaid
flowchart LR
    UI[Vue 3 frontend] --> API[FastAPI API]
    API --> ScopeService[ScopeService]
    ScopeService --> ScopeGuard[ScopeGuard]
    ScopeService --> DB[(PostgreSQL)]

    API --> JobEventHub[JobEventHub]
    API --> ScanRunner[ScanRunner]
    ScanRunner --> ScopeService
    ScanRunner --> Scanner[TcpConnectScanner]
    Scanner --> ScopeGuard
    Scanner --> Targets[Authorized targets]

    ScanRunner --> Fingerprint[fingerprint_service]
    Fingerprint --> Engine[FingerprintEngine]
    Fingerprint --> HttpProbe[HTTP probe]
    ScanRunner --> Enricher[Enricher]
    Enricher --> TLS[TLS certificate probe]

    ScanRunner --> DB
    API --> Search[Search DSL compiler]
    Search --> DB
    JobEventHub --> UI
```

## System Flow

1. An operator creates an engagement with a signed authorization reference and
   an active time window.
2. The operator adds allow and deny CIDR scope entries. Deny rules always
   override allow rules.
3. The operator submits a scan job. `ScopeService.plan_job()` loads the current
   engagement scope, partitions requested targets into authorized and rejected
   CIDR blocks, applies the configured host-count cap, persists the pending job,
   and writes an audit record.
4. The operator runs the job. The API atomically claims a pending job, records
   `job_started`, and either runs inline (`wait=true`) or schedules a FastAPI
   background task.
5. `ScanRunner` loads a fresh `ScopeGuard`, expands authorized CIDRs into hosts,
   and scans hosts through `TcpConnectScanner`.
6. `TcpConnectScanner.scan_host()` calls `ScopeGuard.assert_authorized()` before
   any network I/O. If a host is not authorized, no socket is opened.
7. Open ports are fingerprinted from banners and targeted HTTP probes, enriched
   with host classification, optional GeoIP, and TLS certificate metadata, then
   upserted into `hosts` and `services`.
8. Job progress and terminal status are committed and published through
   `JobEventHub` to WebSocket clients.
9. Operators use host listing, host detail, the scoped search DSL, and the audit
   endpoint to review results.

## Scan Sequence

```mermaid
sequenceDiagram
    actor Operator
    participant UI as Vue frontend
    participant API as FastAPI routers
    participant ScopeService
    participant Guard as ScopeGuard
    participant DB as PostgreSQL
    participant Hub as JobEventHub
    participant Runner as ScanRunner
    participant Scanner as TcpConnectScanner
    participant Analysis as Fingerprint + Enricher
    participant Target as Authorized target

    Operator->>UI: Create engagement and scope
    UI->>API: POST /engagements and /scope
    API->>DB: Persist engagement and scope entries

    Operator->>UI: Submit scan job
    UI->>API: POST /engagements/{id}/jobs
    API->>ScopeService: plan_job(job_type, targets, params)
    ScopeService->>DB: Load engagement and scope_entries
    ScopeService->>Guard: filter_targets(requested_targets)

    alt No authorized targets, inactive engagement, or job too large
        ScopeService->>DB: Insert rejected audit_log row
        API-->>UI: 422, 409, or 413 error
    else Authorized target partition exists
        ScopeService->>DB: Insert ScanJob and audit_log row
        API->>Hub: publish pending job
        API-->>UI: Pending ScanJob
    end

    Operator->>UI: Run job
    UI->>API: POST /jobs/{job_id}/run
    API->>DB: Claim pending job as running
    API->>Hub: publish running job
    API->>Runner: run_job(job_id)
    Runner->>ScopeService: load_guard(engagement_id)
    ScopeService->>DB: Load active scope snapshot
    ScopeService-->>Runner: ScopeGuard
    Runner->>Scanner: scan_host(ip, ports)
    Scanner->>Guard: assert_authorized(ip)
    Guard-->>Scanner: authorized decision
    Scanner->>Target: TCP connect per port
    Target-->>Scanner: state, latency, optional banner
    Scanner-->>Runner: HostResult
    Runner->>Analysis: fingerprint_service() and enrich host/services
    Analysis-->>Runner: Fingerprint, TLS, geo/tags
    Runner->>DB: Upsert Host and Service rows
    Runner->>DB: Update ScanJob stats and audit lifecycle
    Runner->>Hub: publish progress and completed/failed job
    Hub-->>UI: jobs.snapshot and job.updated events
```

## Main Class Diagram

```mermaid
classDiagram
    direction LR

    class Engagement {
        +UUID id
        +str client_name
        +str authorization_ref
        +datetime starts_at
        +datetime ends_at
        +bool is_active
    }

    class ScopeEntryRow {
        +UUID id
        +CIDR cidr
        +ScopeKind kind
        +datetime expires_at
    }

    class ScanJob {
        +UUID id
        +JobType job_type
        +JobStatus status
        +list requested_targets
        +list authorized_targets
        +list rejected_targets
        +dict stats
    }

    class Host {
        +UUID id
        +INET ip
        +str hostname
        +int asn
        +str country
        +list tags
    }

    class Service {
        +UUID id
        +int port
        +Transport transport
        +str product
        +str version
        +list cpe
        +dict tls
        +TSVECTOR search_vector
    }

    class AuditLog {
        +int id
        +datetime ts
        +AuditAction action
        +str verdict
        +dict detail
    }

    class ScopeService {
        +load_guard()
        +authorize_host()
        +plan_job()
    }

    class ScopeGuard {
        +evaluate()
        +assert_authorized()
        +filter_targets()
        +allow_networks
        +deny_networks
    }

    class ScopeEntry {
        +IPNetwork cidr
        +EntryKind kind
        +datetime expires_at
        +is_active()
    }

    class ScopeResult {
        +list authorized
        +list rejected
        +fully_authorized
        +authorized_host_count()
    }

    class ScanRunner {
        +run_job()
        -_scan_one()
        -_fingerprint_host()
        -_enrich_host()
        -_persist()
    }

    class TcpConnectScanner {
        +scan_host()
        +is_alive()
        -_scan_port()
        -_read_banner()
    }

    class HostResult {
        +str ip
        +bool alive
        +list ports
        +open_ports
    }

    class PortResult {
        +int port
        +str state
        +str banner
        +float latency_ms
        +is_open
    }

    class FingerprintEngine {
        +identify()
    }

    class Observation {
        +int port
        +str transport
        +str banner
        +HttpResponse http
    }

    class Fingerprint {
        +str service
        +str product
        +str version
        +list cpe
        +float confidence
    }

    class Enricher {
        +enrich_host()
        +is_tls_port()
        +enrich_service_tls()
    }

    class HostEnrichment {
        +str country
        +str city
        +int asn
        +str as_org
        +list tags
    }

    class JobEventHub {
        +connect()
        +disconnect()
        +publish_job()
    }

    Engagement "1" --> "*" ScopeEntryRow
    Engagement "1" --> "*" ScanJob
    Engagement "1" --> "*" Host
    Host "1" --> "*" Service
    ScanJob "1" --> "*" AuditLog

    ScopeService --> ScopeGuard
    ScopeService --> ScanJob
    ScopeService --> AuditLog
    ScopeGuard --> ScopeEntry
    ScopeGuard --> ScopeResult

    ScanRunner --> ScopeService
    ScanRunner --> TcpConnectScanner
    TcpConnectScanner --> ScopeGuard
    TcpConnectScanner --> HostResult
    HostResult --> PortResult
    ScanRunner --> FingerprintEngine
    FingerprintEngine --> Observation
    FingerprintEngine --> Fingerprint
    ScanRunner --> Enricher
    Enricher --> HostEnrichment
    ScanRunner --> Host
    ScanRunner --> Service
    JobEventHub --> ScanJob
```

## Compact Architecture Sketch

```
                        +---------------------+
   requested targets -> |     ScopeService    | -- audit_log -->  PostgreSQL
                        |  +--------------+    |
                        |  |  ScopeGuard  |    |   pure CIDR arithmetic,
                        |  +--------------+    |   no I/O, fully unit-tested
                        +----------+----------+
                                   | authorized targets only
                                   v
                         ScanJob -> ScanRunner -> TcpConnectScanner
                                   |
                                   v
                        hosts -+- services (tsvector + JSONB)
                               +- enrichment (netclass / geoip / tls)
                                   |
                                   v
                  FastAPI search API -- query DSL -> SQL -- Vue 3 frontend
```

## What Is Implemented

The safety foundation, scan execution path, search surface, and operator UI are
implemented as a vertical slice.

| File | Purpose |
|------|---------|
| `app/scope/guard.py` | **Pure** Scope Guard. CIDR set arithmetic: allow/deny, deny-overrides-allow, partial-coverage partitioning, expiry. No DB/network deps. |
| `app/scope/exceptions.py` | `OutOfScopeError` (the hard gate), `InvalidTargetError`. |
| `app/scope/service.py` | DB-backed bridge: loads a guard from an engagement, audits every decision, plans jobs (authorized vs rejected partition + per-job host cap). |
| `app/db/models.py` | `engagements`, `scope_entries` (native `CIDR`), `hosts`/`services` (`INET`, `JSONB`, `tsvector`), `scan_jobs`, append-only `audit_log`. |
| `app/db/base.py` | Declarative base + Alembic-friendly naming convention. |
| `app/db/session.py` | Async engine + session factory + FastAPI dependency. |
| `app/config.py` | Env-driven settings, incl. `max_authorized_hosts_per_job` safety cap. |
| `app/api/` | FastAPI app factory, routers, Pydantic schemas, dependencies, and in-process WebSocket job fan-out. |
| `app/scan/runner.py` | Job runner: claims/runs jobs, expands authorized targets, tracks progress, fingerprints/enriches, persists results, and audits lifecycle. |
| `app/scan/scanner.py` | Async TCP connect scanner. Enforces `ScopeGuard.assert_authorized()` before any socket is opened. |
| `app/fingerprint/` | Service fingerprint engine, curated signatures, and HTTP(S) probing for request-first services. |
| `app/enrich/` | Host network classification, optional GeoIP integration, and TLS certificate enrichment. |
| `app/search/` | Query DSL lexer/parser/compiler that produces scoped, parameterized SQLAlchemy queries. |
| `frontend/src/` | Vue 3 UI for search, hosts, jobs/progress, engagements/scope, and audit. |
| `tests/` | Unit and integration coverage for scope, scanner, fingerprinting, enrichment, search, API flow, and job events. |

### Authorization model

A target host `T` is in scope **iff** it is covered by an active `allow`
block **and** not covered by any active `deny` block. `deny` always wins —
this mirrors how SOWs are written ("scan 10.0.0.0/16 *except* 10.0.5.0/24").

Two entry points:
- `ScopeGuard.assert_authorized(ip)` — the per-host gate the worker calls
  immediately before sending any packet. Raises `OutOfScopeError`.
- `ScopeService.plan_job(...)` — submission-time planner that partitions a
  requested target spec into authorized networks and the rejected remainder,
  persists a `ScanJob`, and writes the audit trail.

## Run the tests

```bash
pip install -e ".[dev]"
pytest -q
```

## Local database

```bash
docker compose up -d db
```

```bash
# backend
pip install -r requirements.txt && ./run_api.sh
# frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## GeoIP / ASN enrichment

ReconHive can enrich globally routable hosts with MaxMind GeoLite2 City and ASN
data. The app reads binary `.mmdb` paths from:

```bash
RECONHIVE_GEOIP_CITY_DB=data/geoip/GeoLite2-City.mmdb
RECONHIVE_GEOIP_ASN_DB=data/geoip/GeoLite2-ASN.mmdb
```

Download/update the local databases with your MaxMind account credentials:

```bash
export RECONHIVE_MAXMIND_ACCOUNT_ID=your_account_id
export RECONHIVE_MAXMIND_LICENSE_KEY=your_license_key
scripts/download_geoip_dbs.sh
```

For Docker Compose, the same host directory is mounted into the API container at
`/geoip`, and compose sets the container paths automatically.
