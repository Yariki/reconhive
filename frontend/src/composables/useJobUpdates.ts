import { onBeforeUnmount, ref, watch, type Ref } from 'vue'
import client from '../api/client'
import type { JobStatus, ScanJob } from '../types/api'

export type JobLiveState = 'connecting' | 'connected' | 'reconnecting' | 'disconnected'

interface JobUpdateHandlers {
  onJob: (job: ScanJob) => void
  onSnapshot: (jobs: ScanJob[]) => void
  onConnected: (engagementId: string) => void
}

const jobStatuses = new Set<JobStatus>([
  'pending', 'authorizing', 'running', 'completed', 'failed', 'cancelled',
])

function isScanJob(value: unknown): value is ScanJob {
  if (!value || typeof value !== 'object') return false
  const job = value as Partial<ScanJob>
  return typeof job.id === 'string'
    && typeof job.engagement_id === 'string'
    && typeof job.status === 'string'
    && jobStatuses.has(job.status as JobStatus)
    && typeof job.created_at === 'string'
    && typeof job.updated_at === 'string'
    && Array.isArray(job.authorized_targets)
    && Array.isArray(job.rejected_targets)
}

export function useJobUpdates(
  engagementId: Ref<string | null>,
  handlers: JobUpdateHandlers,
) {
  const liveState = ref<JobLiveState>('disconnected')
  let socket: WebSocket | null = null
  let reconnectTimer: number | undefined
  let reconnectAttempt = 0
  let generation = 0

  function clearReconnectTimer() {
    if (reconnectTimer !== undefined) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = undefined
    }
  }

  function disconnect() {
    generation += 1
    clearReconnectTimer()
    reconnectAttempt = 0
    const activeSocket = socket
    socket = null
    if (activeSocket && activeSocket.readyState < WebSocket.CLOSING) {
      activeSocket.close(1000, 'view closed')
    }
    liveState.value = 'disconnected'
  }

  function connect(id: string) {
    clearReconnectTimer()
    const connectionGeneration = ++generation
    liveState.value = reconnectAttempt ? 'reconnecting' : 'connecting'

    const nextSocket = new WebSocket(client.jobsWebSocketUrl(id))
    socket = nextSocket

    nextSocket.onopen = () => {
      if (connectionGeneration !== generation || engagementId.value !== id) {
        nextSocket.close(1000, 'stale engagement')
        return
      }
      liveState.value = 'connected'
      reconnectAttempt = 0
      handlers.onConnected(id)
    }

    nextSocket.onmessage = message => {
      if (connectionGeneration !== generation || engagementId.value !== id) return
      try {
        const event: unknown = JSON.parse(message.data)
        if (!event || typeof event !== 'object') return
        const payload = event as { type?: unknown; job?: unknown; jobs?: unknown }
        if (payload.type === 'job.updated' && isScanJob(payload.job)) {
          handlers.onJob(payload.job)
        }
        if (payload.type === 'jobs.snapshot' && Array.isArray(payload.jobs)) {
          handlers.onSnapshot(payload.jobs.filter(isScanJob))
        }
      } catch {
        // Ignore malformed messages and keep the live connection open.
      }
    }

    nextSocket.onclose = () => {
      if (connectionGeneration !== generation || engagementId.value !== id) return
      socket = null
      liveState.value = 'reconnecting'
      const delay = Math.min(1000 * 2 ** reconnectAttempt, 15_000)
      reconnectAttempt += 1
      reconnectTimer = window.setTimeout(() => {
        if (engagementId.value === id) connect(id)
      }, delay)
    }
  }

  watch(engagementId, id => {
    disconnect()
    if (id) connect(id)
  }, { immediate: true })

  onBeforeUnmount(disconnect)

  return { liveState }
}
