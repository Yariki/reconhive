<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'
import { useAppStore } from './stores/app'

interface NavItem {
  title: string
  icon: string
  to: string
}

const store = useAppStore()
const { engagements, currentId } = storeToRefs(store)
const route = useRoute()

const canRenderRoute = computed(() =>
  Boolean(currentId.value) || route.name === 'engagements'
)

const nav: NavItem[] = [
  { title: 'Search', icon: 'mdi-magnify', to: '/search' },
  { title: 'Hosts', icon: 'mdi-server-network', to: '/hosts' },
  { title: 'Jobs', icon: 'mdi-radar', to: '/jobs' },
  { title: 'Engagements', icon: 'mdi-shield-account', to: '/engagements' },
  { title: 'Audit', icon: 'mdi-clipboard-text-clock', to: '/audit' },
]

onMounted(() => store.loadEngagements())
</script>

<template>
  <v-app>
    <v-navigation-drawer permanent color="surface">
      <div class="pa-4 d-flex align-center">
        <v-icon color="primary" size="28" class="mr-2">mdi-hexagon-multiple</v-icon>
        <span class="text-h6 font-weight-bold">ReconHive</span>
      </div>
      <v-divider />
      <v-list nav density="comfortable">
        <v-list-item v-for="n in nav" :key="n.to" :to="n.to" :prepend-icon="n.icon" :title="n.title" />
      </v-list>
    </v-navigation-drawer>

    <v-app-bar flat color="surface">
      <v-spacer />
      <div style="max-width: 420px; width: 100%" class="mr-4">
        <v-select
          :items="engagements" item-title="client_name" item-value="id"
          :model-value="currentId" @update:model-value="store.setCurrent"
          label="Engagement" density="compact" hide-details variant="outlined"
          prepend-inner-icon="mdi-shield-check"
        />
      </div>
    </v-app-bar>

    <v-main>
      <v-container fluid class="pa-6">
        <router-view v-if="canRenderRoute" />
        <v-alert v-else type="info" variant="tonal" title="Create an engagement to begin">
          <div>Every scan is gated to an engagement's authorized scope.</div>
          <v-btn class="mt-3" color="primary" prepend-icon="mdi-plus" to="/engagements">
            New engagement
          </v-btn>
        </v-alert>
      </v-container>
    </v-main>
  </v-app>
</template>
