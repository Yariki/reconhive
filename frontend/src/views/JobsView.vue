<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import axios from 'axios'
import { useAppStore } from '../stores/app'
import { useJobUpdates } from '../composables/useJobUpdates'
import JobProgress from '../components/JobProgress.vue'
import client from '../api/client'
import type { ScanJob, JobType, JobStatus } from '../types/api'

const store = useAppStore()
const { currentId } = storeToRefs(store)
const jobs = ref<ScanJob[]>([])
const loading = ref(false)
const submitting = ref(false)
const error = ref<string | null>(null)
const startingJobs = ref(new Set<string>())

interface JobForm {
  job_type: JobType
  targets: string
  ports: string
}

const form = ref<JobForm>({ job_type: 'banner_grab', targets: '', ports: '' })
const jobTypes: Array<{ title: string; value: JobType }> = [
  { title: 'Host discovery', value: 'discovery' },
  { title: 'Port scan', value: 'port_scan' },
  { title: 'Banner and service detection', value: 'banner_grab' },
  { title: 'Host and TLS enrichment', value: 'enrich' },
]
const jobTypeInfo: Record<JobType, string> = {
  discovery: 'Reports responsive hosts and the probe ports that confirmed liveness.',
  port_scan: 'Reports open, closed, and filtered ports with connection latency.',
  banner_grab: 'Collects service banners and identifies products, versions, and TLS.',
  enrich: 'Reports IP classification, GeoIP/ASN data when available, and TLS ports.',
}
const statusColor: Record<JobStatus, string> = {
  pending: 'grey',
  authorizing: 'info',
  running: 'info',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
}

function errorMessage(e: unknown): string {
  return axios.isAxiosError(e) ? (e.response?.data?.detail ?? String(e)) : String(e)
}

function upsertJob(incoming: ScanJob) {
  const index = jobs.value.findIndex(job => job.id === incoming.id)
  if (index >= 0) {
    const currentUpdated = Date.parse(jobs.value[index].updated_at)
    const incomingUpdated = Date.parse(incoming.updated_at)
    if (incomingUpdated < currentUpdated) return
    jobs.value[index] = incoming
  } else {
    jobs.value.push(incoming)
  }
  jobs.value.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
}

function mergeJobs(incoming: ScanJob[]) {
  incoming.forEach(upsertJob)
}

function portSummary(job: ScanJob): string | null {
  const scanned = job.stats.ports_scanned
  const total = job.stats.ports_total
  return typeof scanned === 'number' && typeof total === 'number'
    ? `${scanned.toLocaleString()} / ${total.toLocaleString()} ports`
    : null
}

function jobTypeTitle(type: JobType): string {
  return jobTypes.find(option => option.value === type)?.title ?? type
}

async function load(silent = false, engagementId = currentId.value) {
  if (!engagementId) return
  if (!silent) loading.value = true
  try {
    const incoming = await client.listJobs(engagementId)
    if (currentId.value === engagementId) mergeJobs(incoming)
  } catch (e) {
    if (!silent) error.value = errorMessage(e)
  } finally {
    if (!silent && currentId.value === engagementId) loading.value = false
  }
}

async function submit() {
  if (!currentId.value) return
  error.value = null
  submitting.value = true
  try {
    const job = await client.planJob(currentId.value, {
      job_type: form.value.job_type,
      targets: form.value.targets.split(',').map(s => s.trim()).filter(Boolean),
      ports: form.value.ports || null,
    })
    upsertJob(job)
    form.value.targets = ''
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    submitting.value = false
  }
}

async function run(job: ScanJob) {
  error.value = null
  startingJobs.value.add(job.id)
  try {
    upsertJob(await client.runJob(job.id))
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    startingJobs.value.delete(job.id)
  }
}

watch(currentId, engagementId => {
  jobs.value = []
  error.value = null
  if (!engagementId) return
  void load(false, engagementId)
}, { immediate: true })

const { liveState } = useJobUpdates(currentId, {
  onJob: upsertJob,
  onSnapshot: mergeJobs,
  onConnected: engagementId => void load(true, engagementId),
})
const liveLabel = computed(() => ({
  connecting: 'Connecting',
  connected: 'Live',
  reconnecting: 'Reconnecting',
  disconnected: 'Offline',
}[liveState.value]))
const liveColor = computed(() => ({
  connecting: 'info',
  connected: 'success',
  reconnecting: 'warning',
  disconnected: 'grey',
}[liveState.value]))
</script>

<template>
  <v-card variant="outlined" class="mb-6">
    <v-card-title>New scan job</v-card-title>
    <v-card-text>
      <v-row dense>
        <v-col cols="12" md="3">
          <v-select
            v-model="form.job_type"
            :items="jobTypes"
            item-title="title"
            item-value="value"
            label="Type"
            density="compact"
            hide-details
          />
        </v-col>
        <v-col cols="12" md="5">
          <v-text-field v-model="form.targets" label="Targets (comma-separated CIDRs)"
                        placeholder="10.0.0.0/24, 192.168.1.5" density="compact" hide-details />
        </v-col>
        <v-col cols="12" md="2">
          <v-text-field v-model="form.ports" label="Ports" placeholder="1-1024 or blank" density="compact" hide-details />
        </v-col>
        <v-col cols="12" md="2" class="d-flex align-center">
          <v-btn color="primary" block :loading="submitting" @click="submit">Plan job</v-btn>
        </v-col>
      </v-row>
      <v-alert v-if="error" type="error" variant="tonal" class="mt-3">{{ error }}</v-alert>
      <v-alert type="info" variant="tonal" density="compact" class="mt-3">
        {{ jobTypeInfo[form.job_type] }}
      </v-alert>
      <p class="text-caption text-medium-emphasis mt-2">
        Targets are filtered against authorized scope before queuing — out-of-scope ranges are rejected.
      </p>
    </v-card-text>
  </v-card>

  <div class="d-flex align-center mb-3">
    <span class="text-h6 font-weight-bold">Scan jobs</span>
    <v-spacer />
    <v-chip :color="liveColor" size="small" variant="tonal" prepend-icon="mdi-access-point">
      {{ liveLabel }}
    </v-chip>
  </div>
  <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-3" />

  <v-expansion-panels variant="accordion">
    <v-expansion-panel v-for="j in jobs" :key="j.id">
      <v-expansion-panel-title>
        <div class="d-flex align-center ga-3" style="width:100%">
          <v-chip :color="statusColor[j.status]" size="small" variant="flat">{{ j.status }}</v-chip>
          <span>{{ jobTypeTitle(j.job_type) }}</span>
          <span class="text-caption text-medium-emphasis">{{ j.authorized_targets.join(', ') }}</span>
          <span v-if="portSummary(j)" class="text-caption">{{ portSummary(j) }}</span>
          <v-spacer />
          <v-btn v-if="j.status === 'pending'" size="small" color="primary"
                 variant="tonal" :loading="startingJobs.has(j.id)"
                 :disabled="startingJobs.has(j.id)" @click.stop="run(j)">Run</v-btn>
        </div>
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <div class="text-body-2">
          <strong>Authorized:</strong> {{ j.authorized_targets.join(', ') || '—' }}<br>
          <strong>Rejected:</strong>
          <span class="text-error">{{ j.rejected_targets.join(', ') || '—' }}</span><br>
          <span v-if="j.error" class="text-error"><br><strong>Error:</strong> {{ j.error }}</span>
        </div>
        <v-divider class="my-4" />
        <JobProgress :job="j" />
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>
