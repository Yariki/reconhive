import axios from 'axios'
import type {
  Engagement, EngagementCreate,
  ScopeEntry, ScopeEntryCreate,
  ScanJob, ScanJobCreate,
  HostSummary, Host,
  SearchResult,
  AuditEntry,
} from '../types/api'

const apiBase = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
const api = axios.create({ baseURL: apiBase })

function jobsWebSocketUrl(engagementId: string): string {
  const url = new URL(apiBase, window.location.origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = `${url.pathname.replace(/\/$/, '')}/ws/engagements/${engagementId}/jobs`
  url.search = ''
  url.hash = ''
  return url.toString()
}

export default {
  listEngagements: (): Promise<Engagement[]> =>
    api.get('/engagements').then(r => r.data),

  createEngagement: (body: EngagementCreate): Promise<Engagement> =>
    api.post('/engagements', body).then(r => r.data),

  getEngagement: (id: string): Promise<Engagement> =>
    api.get(`/engagements/${id}`).then(r => r.data),

  listScope: (id: string): Promise<ScopeEntry[]> =>
    api.get(`/engagements/${id}/scope`).then(r => r.data),

  addScope: (id: string, body: ScopeEntryCreate): Promise<ScopeEntry> =>
    api.post(`/engagements/${id}/scope`, body).then(r => r.data),

  listJobs: (id: string): Promise<ScanJob[]> =>
    api.get(`/engagements/${id}/jobs`).then(r => r.data),

  planJob: (id: string, body: ScanJobCreate): Promise<ScanJob> =>
    api.post(`/engagements/${id}/jobs`, body).then(r => r.data),

  runJob: (jobId: string, wait = false): Promise<ScanJob> =>
    api.post(`/jobs/${jobId}/run`, null, { params: { wait } }).then(r => r.data),

  jobsWebSocketUrl,

  listHosts: (id: string): Promise<HostSummary[]> =>
    api.get(`/engagements/${id}/hosts`).then(r => r.data),

  getHost: (hostId: string): Promise<Host> =>
    api.get(`/hosts/${hostId}`).then(r => r.data),

  search: (id: string, q: string, limit = 50): Promise<SearchResult[]> =>
    api.get(`/engagements/${id}/search`, { params: { q, limit } }).then(r => r.data),

  listAudit: (id: string): Promise<AuditEntry[]> =>
    api.get(`/engagements/${id}/audit`).then(r => r.data),
}
