<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import axios from 'axios'
import { useAppStore } from '../stores/app'
import client from '../api/client'
import type { Engagement, ScopeEntry, ScopeKind } from '../types/api'

const store = useAppStore()
const { engagements, currentId, current } = storeToRefs(store)

// ── dialog ──────────────────────────────────────────────────────────────────
const dialog = ref(false)
const creating = ref(false)
const formError = ref<string | null>(null)

interface EngForm {
  client_name: string
  authorization_ref: string
  contact: string
  notes: string
  starts_at: string
  ends_at: string
}

function defaultForm(): EngForm {
  const today = new Date()
  const ends = new Date(today.getTime() + 30 * 86_400_000)
  return {
    client_name: '',
    authorization_ref: '',
    contact: '',
    notes: '',
    starts_at: today.toISOString().slice(0, 10),
    ends_at: ends.toISOString().slice(0, 10),
  }
}

const form = ref<EngForm>(defaultForm())

function openDialog() {
  form.value = defaultForm()
  formError.value = null
  dialog.value = true
}

// Parse "YYYY-MM-DD" as local midnight to avoid UTC-offset surprises
function localISO(dateStr: string): string {
  return new Date(`${dateStr}T00:00:00`).toISOString()
}

async function createEngagement() {
  if (!form.value.client_name.trim() || !form.value.authorization_ref.trim()) {
    formError.value = 'Client name and authorization ref are required.'
    return
  }
  if (form.value.ends_at <= form.value.starts_at) {
    formError.value = 'End date must be after start date.'
    return
  }
  formError.value = null
  creating.value = true
  try {
    const eng = await client.createEngagement({
      client_name: form.value.client_name.trim(),
      authorization_ref: form.value.authorization_ref.trim(),
      contact: form.value.contact.trim() || null,
      notes: form.value.notes.trim() || null,
      starts_at: localISO(form.value.starts_at),
      ends_at: localISO(form.value.ends_at),
    })
    dialog.value = false
    await store.loadEngagements()
    store.setCurrent(eng.id)
    await loadScope()
  } catch (e) {
    formError.value = axios.isAxiosError(e) ? (e.response?.data?.detail ?? String(e)) : String(e)
  } finally {
    creating.value = false
  }
}

// ── engagements table ────────────────────────────────────────────────────────
const engHeaders = [
  { title: 'Client', key: 'client_name' },
  { title: 'Auth ref', key: 'authorization_ref' },
  { title: 'Contact', key: 'contact' },
  { title: 'Starts', key: 'starts_at' },
  { title: 'Ends', key: 'ends_at' },
  { title: 'Status', key: 'is_active', align: 'center' as const },
]

function fmtDate(iso: string): string {
  return iso.slice(0, 10)
}

function rowProps({ item }: { item: Engagement }) {
  return {
    class: item.id === currentId.value ? 'selected-row' : '',
    style: 'cursor:pointer',
  }
}

function onRowClick(_: Event, { item }: { item: Engagement }) {
  store.setCurrent(item.id)
}

// ── scope ────────────────────────────────────────────────────────────────────
const scope = ref<ScopeEntry[]>([])
const newScope = ref<{ cidr: string; kind: ScopeKind }>({ cidr: '', kind: 'allow' })
const scopeKinds: ScopeKind[] = ['allow', 'deny']
const scopeError = ref<string | null>(null)

async function loadScope() {
  if (!currentId.value) { scope.value = []; return }
  scope.value = await client.listScope(currentId.value)
}

async function addScope() {
  if (!currentId.value) return
  scopeError.value = null
  try {
    await client.addScope(currentId.value, { ...newScope.value })
    newScope.value.cidr = ''
    await loadScope()
  } catch (e) {
    scopeError.value = axios.isAxiosError(e) ? (e.response?.data?.detail ?? String(e)) : String(e)
  }
}

onMounted(() => {
  store.loadEngagements()
  loadScope()
})
watch(currentId, loadScope)
</script>

<template>
  <div>
    <div class="d-flex align-center mb-4">
      <span class="text-h6 font-weight-bold">Engagements</span>
      <v-spacer />
      <v-btn color="primary" prepend-icon="mdi-plus" @click="openDialog">New engagement</v-btn>
    </div>

    <v-card variant="outlined" class="mb-6">
      <v-data-table
        :headers="engHeaders"
        :items="engagements"
        density="comfortable"
        :row-props="rowProps"
        @click:row="onRowClick"
        no-data-text="No engagements yet — create one to begin."
      >
        <template #item.starts_at="{ item }">{{ fmtDate(item.starts_at) }}</template>
        <template #item.ends_at="{ item }">{{ fmtDate(item.ends_at) }}</template>
        <template #item.is_active="{ item }">
          <v-chip :color="item.is_active ? 'success' : 'grey'" size="x-small" variant="flat">
            {{ item.is_active ? 'active' : 'inactive' }}
          </v-chip>
        </template>
      </v-data-table>
    </v-card>

    <v-card v-if="currentId" variant="outlined">
      <v-card-title>
        Authorized scope
        <span class="text-body-2 text-medium-emphasis ml-2">{{ current?.client_name }}</span>
      </v-card-title>
      <v-card-text>
        <div class="d-flex ga-2 mb-3">
          <v-text-field v-model="newScope.cidr" label="CIDR" placeholder="10.0.0.0/16"
                        density="compact" hide-details />
          <v-select v-model="newScope.kind" :items="scopeKinds" label="Kind"
                    density="compact" hide-details style="max-width:120px" />
          <v-btn color="primary" @click="addScope">Add</v-btn>
        </div>
        <v-alert v-if="scopeError" type="error" variant="tonal" class="mb-3" density="compact">
          {{ scopeError }}
        </v-alert>
        <v-list density="compact">
          <v-list-item v-for="s in scope" :key="s.id">
            <template #prepend>
              <v-icon :color="s.kind === 'allow' ? 'success' : 'error'">
                {{ s.kind === 'allow' ? 'mdi-check-circle' : 'mdi-cancel' }}
              </v-icon>
            </template>
            <v-list-item-title>{{ s.cidr }}</v-list-item-title>
            <v-list-item-subtitle>{{ s.kind }}</v-list-item-subtitle>
          </v-list-item>
          <v-list-item v-if="!scope.length">
            <v-list-item-subtitle>No scope yet — add a CIDR to authorize scanning.</v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <v-dialog v-model="dialog" max-width="560" persistent>
      <v-card>
        <v-card-title class="d-flex align-center pt-4 px-6">
          New engagement
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="dialog = false" />
        </v-card-title>

        <v-card-text class="px-6">
          <v-text-field
            v-model="form.client_name"
            label="Client name *"
            density="compact"
            class="mb-3"
            autofocus
          />
          <v-text-field
            v-model="form.authorization_ref"
            label="Authorization ref — SOW / RoE number *"
            density="compact"
            class="mb-3"
          />
          <v-text-field
            v-model="form.contact"
            label="Contact (optional)"
            density="compact"
            class="mb-3"
          />
          <v-row dense class="mb-1">
            <v-col cols="6">
              <v-text-field
                v-model="form.starts_at"
                label="Starts"
                type="date"
                density="compact"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="form.ends_at"
                label="Ends"
                type="date"
                density="compact"
              />
            </v-col>
          </v-row>
          <v-textarea
            v-model="form.notes"
            label="Notes (optional)"
            density="compact"
            rows="2"
            auto-grow
          />
          <v-alert v-if="formError" type="error" variant="tonal" density="compact" class="mt-2">
            {{ formError }}
          </v-alert>
        </v-card-text>

        <v-card-actions class="px-6 pb-4">
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">Cancel</v-btn>
          <v-btn color="primary" :loading="creating" @click="createEngagement">Create</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<style scoped>
.selected-row {
  background: rgba(47, 129, 247, 0.08);
}
</style>
