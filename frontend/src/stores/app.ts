import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import client from '../api/client'
import type { Engagement } from '../types/api'

export const useAppStore = defineStore('app', () => {
  const engagements = ref<Engagement[]>([])
  const currentId = ref<string | null>(localStorage.getItem('reconhive.engagementId'))
  const loading = ref(false)
  const error = ref<string | null>(null)

  const current = computed(() =>
    engagements.value.find(e => e.id === currentId.value) ?? null
  )

  async function loadEngagements() {
    loading.value = true
    try {
      engagements.value = await client.listEngagements()
      error.value = null

      const selectionExists = engagements.value.some(e => e.id === currentId.value)
      if (!selectionExists) {
        if (engagements.value.length) {
          setCurrent(engagements.value[0].id)
        } else {
          currentId.value = null
          localStorage.removeItem('reconhive.engagementId')
        }
      }
    } catch (e) {
      error.value = String(e)
    } finally {
      loading.value = false
    }
  }

  function setCurrent(id: string) {
    currentId.value = id
    localStorage.setItem('reconhive.engagementId', id)
  }

  return { engagements, currentId, loading, error, current, loadEngagements, setCurrent }
})
