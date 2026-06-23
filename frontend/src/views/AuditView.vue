<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useAppStore } from '../stores/app'
import client from '../api/client'
import type { AuditEntry } from '../types/api'

const store = useAppStore()
const { currentId } = storeToRefs(store)
const rows = ref<AuditEntry[]>([])
const loading = ref(false)

const headers = [
  { title: 'Time', key: 'ts' },
  { title: 'Actor', key: 'actor' },
  { title: 'Action', key: 'action' },
  { title: 'Target', key: 'target' },
  { title: 'Verdict', key: 'verdict' },
  { title: 'Reason', key: 'reason' },
]

const verdictColor: Record<string, string> = {
  authorized: 'success',
  denied: 'error',
  rejected: 'error',
  not_in_allowlist: 'warning',
  partial: 'warning',
  completed: 'success',
  failed: 'error',
}

async function load() {
  if (!currentId.value) return
  loading.value = true
  try {
    rows.value = await client.listAudit(currentId.value)
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(currentId, load)
</script>

<template>
  <v-card variant="outlined">
    <v-card-title>Audit trail</v-card-title>
    <v-data-table :headers="headers" :items="rows" :loading="loading" density="compact">
      <template #item.ts="{ item }">{{ item.ts?.slice(0, 19).replace('T', ' ') }}</template>
      <template #item.verdict="{ item }">
        <v-chip v-if="item.verdict" :color="verdictColor[item.verdict] ?? 'grey'"
                size="x-small" variant="flat">{{ item.verdict }}</v-chip>
      </template>
    </v-data-table>
  </v-card>
</template>
