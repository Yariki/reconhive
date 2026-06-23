<script setup lang="ts">
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import axios from 'axios'
import { useAppStore } from '../stores/app'
import client from '../api/client'
import type { SearchResult } from '../types/api'

const store = useAppStore()
const { currentId } = storeToRefs(store)

const query = ref('')
const results = ref<SearchResult[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const searched = ref(false)

const examples = [
  'port:443 product:nginx',
  'product:OpenSSH country:UA',
  'port:1-1024 has_tls:true',
  'net:10.0.0.0/8 -port:22',
  'service:postgresql',
  '"admin"',
]

async function runSearch() {
  if (!currentId.value) return
  loading.value = true
  error.value = null
  searched.value = true
  try {
    results.value = await client.search(currentId.value, query.value)
  } catch (e) {
    error.value = axios.isAxiosError(e) ? (e.response?.data?.detail ?? String(e)) : String(e)
    results.value = []
  } finally {
    loading.value = false
  }
}

function useExample(ex: string) {
  query.value = ex
  runSearch()
}

function flag(cc: string | null | undefined): string {
  if (!cc || cc.length !== 2) return ''
  return String.fromCodePoint(...[...cc.toUpperCase()].map(c => 0x1f1a5 + c.charCodeAt(0)))
}
</script>

<template>
  <div>
    <v-text-field
      v-model="query" @keyup.enter="runSearch"
      placeholder='Search: port:443 product:nginx country:UA "admin"'
      prepend-inner-icon="mdi-magnify" variant="solo-filled" hide-details
      clearable density="comfortable"
    >
      <template #append>
        <v-btn color="primary" :loading="loading" @click="runSearch">Search</v-btn>
      </template>
    </v-text-field>

    <div class="mt-3 d-flex flex-wrap ga-2">
      <v-chip v-for="ex in examples" :key="ex" size="small" variant="outlined"
              @click="useExample(ex)">{{ ex }}</v-chip>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" class="mt-4">{{ error }}</v-alert>

    <div v-if="searched && !loading" class="text-caption text-medium-emphasis mt-4">
      {{ results.length }} result(s)
    </div>

    <v-row class="mt-1">
      <v-col v-for="r in results" :key="r.service.id" cols="12">
        <v-card variant="outlined">
          <v-card-text>
            <div class="d-flex align-center flex-wrap ga-2">
              <span class="text-h6 font-weight-bold">{{ r.host.ip }}</span>
              <v-chip size="small" color="primary" variant="flat">
                {{ r.service.port }}/{{ r.service.transport }}
              </v-chip>
              <v-chip v-if="r.service.product" size="small" color="secondary" variant="tonal">
                {{ r.service.product }}<template v-if="r.service.version"> {{ r.service.version }}</template>
              </v-chip>
              <span v-if="r.host.country" class="text-body-2">
                {{ flag(r.host.country) }} {{ r.host.country }}
              </span>
              <span v-if="r.host.as_org" class="text-caption text-medium-emphasis">
                AS{{ r.host.asn }} {{ r.host.as_org }}
              </span>
              <v-spacer />
              <v-icon v-if="r.service.tls" color="success" title="TLS">mdi-lock</v-icon>
            </div>

            <div class="mt-2 d-flex flex-wrap ga-1">
              <v-chip v-for="t in r.host.tags" :key="t" size="x-small" variant="outlined">{{ t }}</v-chip>
              <v-chip v-for="c in r.service.cpe" :key="c" size="x-small" color="info" variant="tonal">{{ c }}</v-chip>
            </div>

            <pre v-if="r.service.banner" class="banner mt-2">{{ r.service.banner }}</pre>

            <div v-if="r.service.tls" class="text-caption text-medium-emphasis mt-2">
              TLS: {{ r.service.tls.subject?.['CN'] }} · issuer {{ r.service.tls.issuer?.['CN'] }}
              <template v-if="r.service.tls.not_after"> · expires {{ r.service.tls.not_after.slice(0, 10) }}</template>
            </div>

            <RouterLink :to="`/hosts/${r.host.id}`" class="text-caption">view host →</RouterLink>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-alert v-if="searched && !loading && !results.length && !error"
             type="info" variant="tonal" class="mt-4">No services matched.</v-alert>
  </div>
</template>

<style scoped>
.banner {
  background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
  padding: 8px 10px; font-size: 12px; white-space: pre-wrap; word-break: break-all;
  max-height: 160px; overflow: auto; margin: 0;
}
</style>
