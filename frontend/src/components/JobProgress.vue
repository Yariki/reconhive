<script setup lang="ts">
import { computed } from 'vue'
import type {
  JobEnrichmentFinding,
  JobHostFinding,
  JobPortProgress,
  JobServiceFinding,
  ScanJob,
} from '../types/api'

const props = defineProps<{ job: ScanJob }>()

const numberStat = (key: keyof ScanJob['stats']) => {
  const value = props.job.stats[key]
  return typeof value === 'number' ? value : 0
}

const primaryTotal = computed(() => ['discovery', 'enrich'].includes(props.job.job_type)
  ? numberStat('hosts_total')
  : numberStat('ports_total'))
const primaryCompleted = computed(() => {
  if (props.job.job_type === 'discovery') return numberStat('hosts_scanned')
  if (props.job.job_type === 'enrich') return numberStat('hosts_analyzed')
  return numberStat('ports_scanned')
})
const progressUnit = computed(() => ['discovery', 'enrich'].includes(props.job.job_type)
  ? 'hosts'
  : 'ports')
const progressPercent = computed(() => primaryTotal.value
  ? Math.min(100, Math.round(primaryCompleted.value / primaryTotal.value * 100))
  : 0)
const activityLabel = computed(() => {
  if (props.job.status === 'failed') return 'Scan failed'
  if (props.job.status === 'completed') return 'Scan completed'
  return {
    discovery: 'Discovering live hosts',
    port_scan: 'Scanning ports',
    banner_grab: 'Collecting banners and identifying services',
    enrich: 'Enriching hosts and TLS services',
  }[props.job.job_type]
})

function isPortProgress(value: unknown): value is JobPortProgress {
  if (!value || typeof value !== 'object') return false
  const result = value as Partial<JobPortProgress>
  return typeof result.ip === 'string'
    && typeof result.port === 'number'
    && typeof result.transport === 'string'
    && ['open', 'closed', 'filtered'].includes(result.state ?? '')
}

function isServiceFinding(value: unknown): value is JobServiceFinding {
  if (!value || typeof value !== 'object') return false
  const finding = value as Partial<JobServiceFinding>
  return typeof finding.ip === 'string'
    && typeof finding.port === 'number'
    && typeof finding.transport === 'string'
}

function isHostFinding(value: unknown): value is JobHostFinding {
  if (!value || typeof value !== 'object') return false
  const finding = value as Partial<JobHostFinding>
  return typeof finding.ip === 'string'
    && typeof finding.alive === 'boolean'
    && Array.isArray(finding.open_ports)
    && typeof finding.error === 'boolean'
}

function isEnrichmentFinding(value: unknown): value is JobEnrichmentFinding {
  if (!value || typeof value !== 'object') return false
  const finding = value as Partial<JobEnrichmentFinding>
  return typeof finding.ip === 'string'
    && Array.isArray(finding.tags)
    && Array.isArray(finding.tls_ports)
}

const recentPorts = computed(() => {
  const results = props.job.stats.port_results
  return Array.isArray(results)
    ? results.filter(isPortProgress).slice(-50).reverse()
    : []
})
const services = computed(() => {
  const findings = props.job.stats.services
  return Array.isArray(findings) ? findings.filter(isServiceFinding) : []
})
const hosts = computed(() => {
  const findings = props.job.stats.host_results
  return Array.isArray(findings) ? findings.filter(isHostFinding) : []
})
const enrichments = computed(() => {
  const findings = props.job.stats.enrichments
  return Array.isArray(findings) ? findings.filter(isEnrichmentFinding) : []
})
const portStates = computed(() => {
  const states = props.job.stats.port_states
  return states && typeof states === 'object' ? states : {}
})
const identifiedServices = computed(() => services.value.filter(
  service => service.product || service.service,
).length)
const tlsServices = computed(() => services.value.filter(service => service.tls).length)
const geolocatedHosts = computed(() => enrichments.value.filter(
  enrichment => enrichment.country || enrichment.city || enrichment.asn,
).length)
const stateColor: Record<JobPortProgress['state'], string> = {
  open: 'success',
  closed: 'grey',
  filtered: 'warning',
}
</script>

<template>
  <div v-if="primaryTotal" class="mb-5">
    <div class="d-flex justify-space-between text-body-2 mb-1">
      <span>{{ activityLabel }}</span>
      <span>{{ primaryCompleted.toLocaleString() }} / {{ primaryTotal.toLocaleString() }} {{ progressUnit }}</span>
    </div>
    <v-progress-linear
      :model-value="progressPercent"
      :color="job.status === 'failed' ? 'error' : 'primary'"
      height="8"
      rounded
    />
    <div v-if="job.job_type === 'discovery'" class="d-flex flex-wrap ga-2 mt-3">
      <v-chip size="small" variant="tonal">{{ numberStat('hosts_scanned') }} / {{ numberStat('hosts_total') }} hosts</v-chip>
      <v-chip size="small" color="success" variant="tonal">{{ numberStat('hosts_up') }} live</v-chip>
      <v-chip v-if="numberStat('errors')" size="small" color="error" variant="tonal">{{ numberStat('errors') }} errors</v-chip>
    </div>
    <div v-else-if="job.job_type === 'port_scan'" class="d-flex flex-wrap ga-2 mt-3">
      <v-chip size="small" color="success" variant="tonal">{{ portStates.open ?? 0 }} open</v-chip>
      <v-chip size="small" variant="tonal">{{ portStates.closed ?? 0 }} closed</v-chip>
      <v-chip size="small" color="warning" variant="tonal">{{ portStates.filtered ?? 0 }} filtered</v-chip>
    </div>
    <div v-else-if="job.job_type === 'banner_grab'" class="d-flex flex-wrap ga-2 mt-3">
      <v-chip size="small" color="success" variant="tonal">{{ services.length }} services</v-chip>
      <v-chip size="small" variant="tonal">{{ identifiedServices }} identified</v-chip>
      <v-chip size="small" color="info" variant="tonal">{{ tlsServices }} TLS</v-chip>
    </div>
    <div v-else class="d-flex flex-wrap ga-2 mt-3">
      <v-chip size="small" color="success" variant="tonal">{{ numberStat('hosts_analyzed') }} enriched</v-chip>
      <v-chip size="small" variant="tonal">{{ geolocatedHosts }} GeoIP / ASN</v-chip>
      <v-chip size="small" color="info" variant="tonal">{{ tlsServices }} TLS services</v-chip>
    </div>
  </div>
  <v-alert v-else-if="job.status === 'running'" type="info" variant="tonal" density="compact" class="mb-4">
    Preparing scanner…
  </v-alert>

  <div v-if="job.job_type === 'discovery' && hosts.length" class="mb-5">
    <div class="text-subtitle-2 mb-2">Discovered hosts</div>
    <v-table density="compact">
      <thead><tr><th>Host</th><th>Status</th><th>Open ports observed</th></tr></thead>
      <tbody>
        <tr v-for="host in hosts" :key="host.ip">
          <td>{{ host.ip }}</td>
          <td>
            <v-chip :color="host.error ? 'error' : host.alive ? 'success' : 'grey'" size="x-small" variant="tonal">
              {{ host.error ? 'error' : host.alive ? 'live' : 'no response' }}
            </v-chip>
          </td>
          <td>{{ host.open_ports.join(', ') || '—' }}</td>
        </tr>
      </tbody>
    </v-table>
    <div v-if="job.stats.host_results_truncated" class="text-caption text-medium-emphasis mt-1">Showing the latest 200 hosts.</div>
  </div>

  <div v-if="job.job_type === 'banner_grab' && services.length" class="mb-5">
    <div class="text-subtitle-2 mb-2">Discovered services</div>
    <v-table density="compact">
      <thead><tr><th>Host</th><th>Port</th><th>Service</th><th>Banner</th><th>Confidence</th></tr></thead>
      <tbody>
        <tr v-for="service in services" :key="`${service.ip}-${service.port}-${service.transport}`">
          <td>{{ service.ip }}</td>
          <td>{{ service.port }}/{{ service.transport }}</td>
          <td>
            {{ service.product || service.service || 'Unknown' }}
            <span v-if="service.version" class="text-medium-emphasis">{{ service.version }}</span>
            <v-chip v-if="service.tls" size="x-small" color="info" variant="tonal" class="ml-1">TLS</v-chip>
          </td>
          <td><code class="banner-preview">{{ service.banner || '—' }}</code></td>
          <td>{{ service.confidence == null ? '—' : `${Math.round(service.confidence * 100)}%` }}</td>
        </tr>
      </tbody>
    </v-table>
    <div v-if="job.stats.services_truncated" class="text-caption text-medium-emphasis mt-1">
      Showing the latest 200 services.
    </div>
  </div>

  <div v-if="job.job_type === 'enrich' && enrichments.length" class="mb-5">
    <div class="text-subtitle-2 mb-2">Host and TLS enrichment</div>
    <v-table density="compact">
      <thead><tr><th>Host</th><th>Location</th><th>ASN / organization</th><th>Classification</th><th>TLS ports</th></tr></thead>
      <tbody>
        <tr v-for="enrichment in enrichments" :key="enrichment.ip">
          <td>{{ enrichment.ip }}</td>
          <td>{{ [enrichment.city, enrichment.country].filter(Boolean).join(', ') || '—' }}</td>
          <td>{{ enrichment.asn ? `AS${enrichment.asn}` : '—' }} <span class="text-medium-emphasis">{{ enrichment.as_org }}</span></td>
          <td><v-chip v-for="tag in enrichment.tags" :key="tag" size="x-small" variant="tonal" class="mr-1">{{ tag }}</v-chip></td>
          <td>{{ enrichment.tls_ports.join(', ') || '—' }}</td>
        </tr>
      </tbody>
    </v-table>
    <div v-if="job.stats.enrichments_truncated" class="text-caption text-medium-emphasis mt-1">Showing the latest 200 hosts.</div>
  </div>

  <div v-if="job.job_type === 'port_scan' && recentPorts.length">
    <div class="text-subtitle-2 mb-2">Recent port results</div>
    <v-table density="compact">
      <thead><tr><th>Host</th><th>Port</th><th>State</th><th>Latency</th></tr></thead>
      <tbody>
        <tr v-for="result in recentPorts" :key="`${result.ip}-${result.port}-${result.transport}`">
          <td>{{ result.ip }}</td>
          <td>{{ result.port }}/{{ result.transport }}</td>
          <td><v-chip :color="stateColor[result.state]" size="x-small" variant="tonal">{{ result.state }}</v-chip></td>
          <td>{{ result.latency_ms == null ? '—' : `${result.latency_ms} ms` }}</td>
        </tr>
      </tbody>
    </v-table>
    <div class="text-caption text-medium-emphasis mt-1">
      Showing the latest {{ recentPorts.length }} results<span v-if="job.stats.port_results_truncated">; older results were omitted</span>.
    </div>
  </div>
</template>

<style scoped>
.banner-preview {
  display: block;
  max-width: 360px;
  max-height: 5rem;
  overflow: hidden;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
