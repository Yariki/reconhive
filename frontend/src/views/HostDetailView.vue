<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import client from '../api/client'
import type { Host } from '../types/api'

const route = useRoute()
const host = ref<Host | null>(null)
const loading = ref(true)

onMounted(async () => {
  const id = Array.isArray(route.params.id) ? route.params.id[0] : route.params.id
  try {
    host.value = await client.getHost(id)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-if="host">
    <div class="d-flex align-center ga-3 mb-4">
      <RouterLink to="/hosts"><v-icon>mdi-arrow-left</v-icon></RouterLink>
      <span class="text-h5 font-weight-bold">{{ host.ip }}</span>
      <v-chip v-if="host.country" size="small">{{ host.country }}</v-chip>
      <span v-if="host.as_org" class="text-caption text-medium-emphasis">AS{{ host.asn }} {{ host.as_org }}</span>
    </div>
    <div class="mb-4 d-flex flex-wrap ga-1">
      <v-chip v-for="t in host.tags" :key="t" size="small" variant="outlined">{{ t }}</v-chip>
    </div>

    <v-row>
      <v-col v-for="s in host.services" :key="s.id" cols="12" md="6">
        <v-card variant="outlined">
          <v-card-title class="d-flex align-center ga-2">
            <v-chip color="primary" variant="flat" size="small">{{ s.port }}/{{ s.transport }}</v-chip>
            <span v-if="s.product">{{ s.product }} {{ s.version }}</span>
            <v-spacer />
            <v-icon v-if="s.tls" color="success">mdi-lock</v-icon>
          </v-card-title>
          <v-card-text>
            <div class="d-flex flex-wrap ga-1 mb-2">
              <v-chip v-for="c in s.cpe" :key="c" size="x-small" color="info" variant="tonal">{{ c }}</v-chip>
            </div>
            <pre v-if="s.banner" class="banner">{{ s.banner }}</pre>
            <pre v-if="s.tls" class="banner mt-2">{{ JSON.stringify(s.tls, null, 2) }}</pre>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
  <v-progress-linear v-else-if="loading" indeterminate />
</template>

<style scoped>
.banner { background:#0d1117; border:1px solid #30363d; border-radius:6px; padding:8px 10px;
  font-size:12px; white-space:pre-wrap; word-break:break-all; max-height:240px; overflow:auto; margin:0; }
</style>
