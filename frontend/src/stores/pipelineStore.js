import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { jobsApi } from '../api/index.js'

const POLL_MS = 900

export const NODE_META = {
  platform: { label: 'NewsPlatform', short: 'NP', color: '#2dd4bf' },
  deepseek: { label: 'DeepSeek', short: 'DS', color: '#38bdf8' },
  tavily: { label: 'Tavily', short: 'TV', color: '#818cf8' },
  openai: { label: 'OpenAI', short: 'OA', color: '#34d399' },
  qwen: { label: 'Qwen', short: 'QW', color: '#fb7185' },
  openrouter: { label: 'Grok Video', short: 'GR', color: '#fbbf24' },
  github: { label: 'GitHub', short: 'GH', color: '#94a3b8' },
  storage: { label: 'Storage', short: 'ST', color: '#64748b' },
}

/** @param {string} nodeId */
export function nodeMeta(nodeId) {
  return NODE_META[nodeId] || { label: nodeId, short: nodeId.slice(0, 2).toUpperCase(), color: '#64748b' }
}

export const usePipelineStore = defineStore('pipeline', () => {
  const open = ref(false)
  const celeryTaskId = ref(null)
  const title = ref('')
  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)
  let pollTimer = null

  const events = computed(() => data.value?.events || [])
  const progress = computed(() => data.value?.progress ?? 0)
  const currentDetail = computed(() => data.value?.current_detail || '')
  const status = computed(() => data.value?.status || 'running')
  const isTerminal = computed(() => status.value === 'done' || status.value === 'error')

  const activeNodes = computed(() => {
    const set = new Set(['platform'])
    for (const ev of events.value) {
      if (ev.from_node) set.add(ev.from_node)
      if (ev.to_node) set.add(ev.to_node)
    }
    return set
  })

  const activeEdge = computed(() => {
    const running = [...events.value].reverse().find((e) => e.status === 'running')
    if (!running) return null
    return { from: running.from_node, to: running.to_node, id: running.id }
  })

  async function fetchOnce() {
    if (!celeryTaskId.value) return
    try {
      const { data: payload } = await jobsApi.pipeline(celeryTaskId.value)
      data.value = payload
      error.value = null
      if (payload.status === 'done' || payload.status === 'error') {
        stopPolling()
      }
    } catch (err) {
      if (err.response?.status !== 404) {
        error.value = 'Не удалось загрузить детали пайплайна'
      }
    } finally {
      loading.value = false
    }
  }

  function startPolling() {
    if (pollTimer) return
    pollTimer = setInterval(fetchOnce, POLL_MS)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  /** @param {{ celeryTaskId: string, title?: string }} item */
  async function openFor(item) {
    if (!item?.celeryTaskId) return
    celeryTaskId.value = item.celeryTaskId
    title.value = item.title || 'Пайплайн задачи'
    open.value = true
    loading.value = true
    error.value = null
    data.value = null
    await fetchOnce()
    if (!isTerminal.value) startPolling()
  }

  function applyWsUpdate(payload) {
    if (!payload?.celery_task_id) return
    if (data.value && data.value.celery_task_id === payload.celery_task_id) {
      data.value = {
        ...data.value,
        progress: payload.progress ?? data.value.progress,
        current_detail: payload.current_detail ?? data.value.current_detail,
        status: payload.status ?? data.value.status,
      }
    }
    if (open.value && celeryTaskId.value === payload.celery_task_id) {
      fetchOnce()
    }
  }

  function close() {
    open.value = false
    stopPolling()
    celeryTaskId.value = null
    data.value = null
    error.value = null
  }

  function reset() {
    close()
  }

  return {
    open,
    celeryTaskId,
    title,
    data,
    loading,
    error,
    events,
    progress,
    currentDetail,
    status,
    isTerminal,
    activeNodes,
    activeEdge,
    openFor,
    close,
    fetchOnce,
    applyWsUpdate,
    reset,
    stopPolling,
  }
})
