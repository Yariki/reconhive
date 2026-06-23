<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useAppStore } from '../stores/app'
import client from '../api/client'
import type { HostSummary } from '../types/api'

const store = useAppStore()
const { currentId } = storeToRefs(store)
const hosts = ref<HostSummary[]>([])
const loading = ref(false)

const headers = [
  { title: 'IP', key: 'ip' },
  { title: 'Country', key: 'country' },
  { title: 'ASN', key: 'asn' },
  { title: 'Org', key: 'as_org' },
  { title: 'Tags', key: 'tags' },
  { title: 'Last seen', key: 'last_seen' },
]

async function load() {
  if (!currentId.value) return
  loading.value = true
  try {
    hosts.value = await client.listHosts(currentId.value)
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(currentId, load)
</script>

<template>
  <v-card variant="outlined">
    <v-data-table :headers="headers" :items="hosts" :loading="loading" density="comfortable">
      <template #item.ip="{ item }">
        <RouterLink :to="`/hosts/${item.id}`" class="text-primary">{{ item.ip }}</RouterLink>
      </template>
      <template #item.tags="{ item }">
        <v-chip v-for="t in item.tags" :key="t" size="x-small" variant="outlined" class="mr-1">{{ t }}</v-chip>
      </template>
      <template #item.last_seen="{ item }">{{ item.last_seen?.slice(0, 19).replace('T', ' ') }}</template>
    </v-data-table>
  </v-card>
</template>
