export type ScopeKind = 'allow' | 'deny'
export type JobStatus = 'pending' | 'authorizing' | 'running' | 'completed' | 'failed' | 'cancelled'
export type JobType = 'discovery' | 'port_scan' | 'banner_grab' | 'enrich'
export type Transport = 'tcp' | 'udp'
export type JobPhase = 'preparing' | 'scanning' | 'analyzing' | 'completed' | 'failed'

export interface JobPortProgress {
  ip: string
  port: number
  transport: string
  state: 'open' | 'closed' | 'filtered'
  latency_ms: number | null
}

export interface JobServiceFinding {
  ip: string
  port: number
  transport: string
  service: string | null
  product: string | null
  version: string | null
  confidence: number | null
  banner: string | null
  tls: boolean
  tls_subject: string | null
}

export interface JobHostFinding {
  ip: string
  alive: boolean
  open_ports: number[]
  open_port_count: number
  error: boolean
}

export interface JobEnrichmentFinding {
  ip: string
  country: string | null
  city: string | null
  asn: number | null
  as_org: string | null
  tags: string[]
  tls_ports: number[]
}

export interface JobStats extends Record<string, unknown> {
  phase?: JobPhase
  hosts_total?: number
  hosts_scanned?: number
  hosts_analyzed?: number
  hosts_up?: number
  ports_total?: number
  ports_scanned?: number
  ports_per_host?: number
  port_states?: Record<string, number>
  open_services?: number
  errors?: number
  current_port?: JobPortProgress | null
  port_results?: JobPortProgress[]
  port_results_truncated?: boolean
  services?: JobServiceFinding[]
  services_truncated?: boolean
  host_results?: JobHostFinding[]
  host_results_truncated?: boolean
  enrichments?: JobEnrichmentFinding[]
  enrichments_truncated?: boolean
}

export interface Engagement {
  id: string
  client_name: string
  authorization_ref: string
  contact: string | null
  starts_at: string
  ends_at: string
  is_active: boolean
  notes: string | null
}

export interface ScopeEntry {
  id: string
  cidr: string
  kind: ScopeKind
  expires_at: string | null
  note: string | null
}

export interface TlsCert {
  subject?: Record<string, string>
  issuer?: Record<string, string>
  not_before?: string
  not_after?: string
  sans?: string[]
  fingerprint?: string
  cipher?: string
}

export interface Service {
  id: string
  port: number
  transport: Transport
  product: string | null
  version: string | null
  extra_info: string | null
  cpe: string[]
  banner: string | null
  tls: TlsCert | null
  data: Record<string, unknown>
  last_seen: string
}

export interface HostSummary {
  id: string
  ip: string
  hostname: string | null
  country: string | null
  city: string | null
  asn: number | null
  as_org: string | null
  os_guess: string | null
  tags: string[]
  last_seen: string
}

export interface Host extends HostSummary {
  services: Service[]
}

export interface SearchResult {
  host: HostSummary
  service: Service
}

export interface ScanJob {
  id: string
  engagement_id: string
  job_type: JobType
  status: JobStatus
  requested_targets: string[]
  authorized_targets: string[]
  rejected_targets: string[]
  requested_by: string
  stats: JobStats
  error: string | null
  created_at: string
  updated_at: string
  started_at: string | null
  finished_at: string | null
}

export interface AuditEntry {
  id: number
  ts: string
  actor: string
  action: string
  target: string | null
  verdict: string | null
  reason: string | null
  detail: Record<string, unknown>
}

export interface EngagementCreate {
  client_name: string
  authorization_ref: string
  contact?: string | null
  starts_at: string
  ends_at: string
  notes?: string | null
}

export interface ScopeEntryCreate {
  cidr: string
  kind: ScopeKind
  expires_at?: string | null
  note?: string | null
}

export interface ScanJobCreate {
  job_type: JobType
  targets: string[]
  ports?: string | null
  requested_by?: string
}
